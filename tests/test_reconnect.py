"""
Reconnection behaviour of the Python side, tested against a fake bridge that
speaks the same protocol as the Lua plugin (two sockets + a port file).
No Lightroom needed.
"""
import asyncio
import json
import time

import pytest

from lightroom_sdk import socket_bridge
from lightroom_sdk.exceptions import ConnectionError as LRConnectionError
from mcp_server.shared.resilient_client import ResilientClientManager, NOT_REACHABLE_MESSAGE


class FakeBridge:
    """Mimics the Lua plugin: Python sends on one socket and reads replies on the other"""

    def __init__(self, port_file, reply=True):
        self.port_file = port_file
        self.reply = reply
        self.received = []
        self._servers = []
        self._writers = []
        self._reply_writer = None

    async def start(self):
        sender = await asyncio.start_server(self._on_sender, "127.0.0.1", 0)
        receiver = await asyncio.start_server(self._on_receiver, "127.0.0.1", 0)
        self._servers = [sender, receiver]
        sender_port = sender.sockets[0].getsockname()[1]
        receiver_port = receiver.sockets[0].getsockname()[1]
        self.port_file.write_text(f"{sender_port},{receiver_port}")

    async def stop(self):
        for server in self._servers:
            server.close()
        for writer in self._writers:
            writer.close()
        for server in self._servers:
            await server.wait_closed()
        self._writers = []
        if self.port_file.exists():
            self.port_file.unlink()

    async def _on_sender(self, reader, writer):
        self._writers.append(writer)
        self._reply_writer = writer

    async def _on_receiver(self, reader, writer):
        self._writers.append(writer)
        while line := await reader.readline():
            message = json.loads(line)
            self.received.append(message["command"])
            if not self.reply:
                continue
            while self._reply_writer is None:
                await asyncio.sleep(0.01)
            response = {"id": message["id"], "success": True, "result": {"message": "pong"}}
            self._reply_writer.write((json.dumps(response) + "\n").encode())
            await self._reply_writer.drain()


@pytest.fixture
def port_file(tmp_path, monkeypatch):
    path = tmp_path / "lightroom_ports.txt"
    monkeypatch.setattr(socket_bridge, "DEFAULT_PORT_FILE", str(path))
    monkeypatch.setenv("LIGHTROOM_MCP_RELAY", "0")  # these tests talk to the plugin directly
    return path


async def test_reconnects_after_bridge_restart(port_file):
    bridge = FakeBridge(port_file)
    await bridge.start()
    manager = ResilientClientManager()
    try:
        assert (await manager.execute_with_retry("system.ping"))["message"] == "pong"

        # Lightroom / the bridge restarts on new ports
        await bridge.stop()
        await asyncio.sleep(0.1)
        bridge = FakeBridge(port_file)
        await bridge.start()

        assert (await manager.execute_with_retry("system.ping"))["message"] == "pong"
    finally:
        await manager.disconnect()
        await bridge.stop()


async def test_fails_fast_with_clear_message_when_lightroom_is_closed(port_file):
    manager = ResilientClientManager()
    start = time.monotonic()
    with pytest.raises(LRConnectionError) as error:
        await manager.execute_with_retry("system.ping")
    assert str(error.value) == NOT_REACHABLE_MESSAGE
    assert time.monotonic() - start < 10


async def test_recovers_once_lightroom_comes_back(port_file):
    manager = ResilientClientManager()
    with pytest.raises(LRConnectionError):
        await manager.execute_with_retry("system.ping")

    bridge = FakeBridge(port_file)
    await bridge.start()
    try:
        assert (await manager.execute_with_retry("system.ping"))["message"] == "pong"
    finally:
        await manager.disconnect()
        await bridge.stop()


async def test_drop_during_command_is_reported_not_retried(port_file):
    bridge = FakeBridge(port_file, reply=False)
    await bridge.start()
    manager = ResilientClientManager()
    try:
        task = asyncio.create_task(manager.execute_with_retry("develop.setValue", timeout=30))
        while not bridge.received:
            await asyncio.sleep(0.01)
        start = time.monotonic()
        await bridge.stop()

        with pytest.raises(LRConnectionError, match="may or may not have been applied"):
            await task
        assert time.monotonic() - start < 5
        assert bridge.received == ["develop.setValue"]
    finally:
        await manager.disconnect()
