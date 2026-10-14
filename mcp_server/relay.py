"""
Lightroom relay: lets several MCP servers (one per Claude session) share Lightroom.

The Lightroom plugin accepts a single client. The relay is that client: it holds the
one connection to the plugin and forwards newline-delimited JSON requests from any
number of local clients, routing each reply back by request id.

Started automatically by the first MCP server that needs Lightroom
(lightroom_sdk.relay_bridge.RelayBridge); exits after IDLE_TIMEOUT seconds without
clients. Run by hand with: python -m mcp_server.relay
"""
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

from lightroom_sdk import LightroomClient
from lightroom_sdk.exceptions import ConnectionError as LRConnectionError, LightroomSDKError
from lightroom_sdk.relay_bridge import RELAY_HOST, RELAY_PORT
from mcp_server.shared.resilient_client import ResilientClientManager

logger = logging.getLogger("lightroom_relay")

IDLE_TIMEOUT = float(os.environ.get("LIGHTROOM_RELAY_IDLE_TIMEOUT", 600))


class Relay:
    def __init__(self, manager: Optional[ResilientClientManager] = None, idle_timeout: float = IDLE_TIMEOUT):
        # The relay itself must talk to the plugin directly, never to another relay
        self.manager = manager or ResilientClientManager(client_factory=lambda: LightroomClient(direct=True))
        self.idle_timeout = idle_timeout
        self.clients = 0
        self.stopped = asyncio.Event()
        self._idle_task: Optional[asyncio.Task] = None
        self._server: Optional[asyncio.base_events.Server] = None

    async def start(self, host: str = RELAY_HOST, port: int = RELAY_PORT) -> int:
        self._server = await asyncio.start_server(self._on_client, host, port)
        self._arm_idle_timer()
        actual = self._server.sockets[0].getsockname()[1]
        logger.info(f"Relay listening on {host}:{actual}")
        return actual

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        await self.manager.disconnect()
        self.stopped.set()

    def _arm_idle_timer(self) -> None:
        if self._idle_task:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_shutdown())

    async def _idle_shutdown(self) -> None:
        await asyncio.sleep(self.idle_timeout)
        if self.clients == 0:
            logger.info("No clients for a while - shutting down")
            await self.stop()

    async def _on_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.clients += 1
        if self._idle_task:
            self._idle_task.cancel()
        logger.info(f"Client connected ({self.clients} now)")
        write_lock = asyncio.Lock()
        tasks = set()
        try:
            while line := await reader.readline():
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    continue
                task = asyncio.create_task(self._handle(request, writer, write_lock))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
        except (ConnectionError, OSError):
            pass
        finally:
            for task in tasks:
                task.cancel()
            self.clients -= 1
            logger.info(f"Client disconnected ({self.clients} left)")
            try:
                writer.close()
            except Exception:
                pass
            if self.clients == 0:
                self._arm_idle_timer()

    async def _handle(self, request: Dict[str, Any], writer: asyncio.StreamWriter, write_lock: asyncio.Lock) -> None:
        request_id = request.get("id")
        try:
            result = await self.manager.execute_with_retry(
                request["command"], request.get("params"), float(request.get("timeout", 30.0)))
            response = {"id": request_id, "success": True, "result": result}
        except LRConnectionError as e:
            response = {"id": request_id, "success": False,
                        "error": {"code": e.code or "CONNECTION_FAILED", "message": str(e)}}
        except LightroomSDKError as e:
            response = {"id": request_id, "success": False,
                        "error": {**(e.details or {}), "code": e.code or "LIGHTROOM_ERROR", "message": str(e)}}
        except Exception as e:
            response = {"id": request_id, "success": False, "error": {"code": "RELAY_ERROR", "message": str(e)}}
        try:
            async with write_lock:
                writer.write((json.dumps(response) + "\n").encode("utf-8"))
                await writer.drain()
        except (ConnectionError, OSError):
            logger.info(f"Client left before the reply to {request.get('command')}")


async def main() -> None:
    relay = Relay()
    try:
        await relay.start()
    except OSError as e:
        logger.info(f"Relay not started (another one is probably running): {e}")
        return
    await relay.stopped.wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    asyncio.run(main())
