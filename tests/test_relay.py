"""
The relay lets several MCP servers share the single Lightroom plugin connection.
Tested against the fake plugin from test_reconnect. No Lightroom needed.
"""
import asyncio
import time

import pytest

from lightroom_sdk import LightroomClient, socket_bridge
from lightroom_sdk.exceptions import ConnectionError as LRConnectionError
from lightroom_sdk.relay_bridge import RelayBridge
from mcp_server.relay import Relay
from mcp_server.shared.resilient_client import ResilientClientManager, NOT_REACHABLE_MESSAGE
from tests.test_reconnect import FakeBridge


class CountingBridge(FakeBridge):
    """Fake plugin that counts client connections, like the real one would refuse a second"""
    connections = 0

    async def _on_receiver(self, reader, writer):
        CountingBridge.connections += 1
        await super()._on_receiver(reader, writer)


@pytest.fixture
def port_file(tmp_path, monkeypatch):
    path = tmp_path / "lightroom_ports.txt"
    monkeypatch.setattr(socket_bridge, "DEFAULT_PORT_FILE", str(path))
    return path


@pytest.fixture
async def relay():
    relay = Relay(idle_timeout=60)
    port = await relay.start(port=0)
    yield relay, port
    await relay.stop()


def session(port):
    """What each Claude session's MCP server does: a manager whose clients go via the relay"""
    def factory():
        client = LightroomClient(direct=False)
        client._bridge = RelayBridge(port=port, auto_start=False)
        return client
    return ResilientClientManager(client_factory=factory)


async def test_two_sessions_share_one_lightroom_connection(port_file, relay):
    _, port = relay
    bridge = CountingBridge(port_file)
    CountingBridge.connections = 0
    await bridge.start()
    first, second = session(port), session(port)
    try:
        replies = await asyncio.gather(*(s.execute_with_retry("system.ping") for s in (first, second, first, second)))
        assert all(r["message"] == "pong" for r in replies)
        assert CountingBridge.connections == 1
        assert len(bridge.received) == 4
    finally:
        await first.disconnect()
        await second.disconnect()
        await bridge.stop()


async def test_unreachable_lightroom_is_reported_once_and_quickly(port_file, relay):
    _, port = relay
    s = session(port)
    start = time.monotonic()
    try:
        with pytest.raises(LRConnectionError) as error:
            await s.execute_with_retry("system.ping")
        assert str(error.value) == NOT_REACHABLE_MESSAGE
        assert time.monotonic() - start < 10
    finally:
        await s.disconnect()


async def test_session_reconnects_after_the_relay_restarts(port_file):
    bridge = FakeBridge(port_file)
    await bridge.start()
    relay = Relay(idle_timeout=60)
    port = await relay.start(port=0)
    s = session(port)
    try:
        assert (await s.execute_with_retry("system.ping"))["message"] == "pong"
        await relay.stop()
        await asyncio.sleep(0.1)
        relay = Relay(idle_timeout=60)
        await relay.start(port=port)
        assert (await s.execute_with_retry("system.ping"))["message"] == "pong"
    finally:
        await s.disconnect()
        await relay.stop()
        await bridge.stop()


async def test_relay_exits_when_idle(port_file):
    relay = Relay(idle_timeout=0.2)
    port = await relay.start(port=0)
    s = session(port)
    bridge = FakeBridge(port_file)
    await bridge.start()
    try:
        await s.execute_with_retry("system.ping")
        await asyncio.sleep(0.4)
        assert not relay.stopped.is_set()  # a client is still connected
        await s.disconnect()
        await asyncio.wait_for(relay.stopped.wait(), timeout=2)
    finally:
        await bridge.stop()
        if not relay.stopped.is_set():
            await relay.stop()
