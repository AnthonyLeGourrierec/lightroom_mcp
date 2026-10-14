"""
Client side of the Lightroom relay (see mcp_server/relay.py).

Speaks the same request/response protocol as SocketBridge, over a single socket to
the local relay, and starts the relay if none is running.
"""
import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from .socket_bridge import SocketBridge

logger = logging.getLogger(__name__)

RELAY_HOST = "127.0.0.1"
RELAY_PORT = int(os.environ.get("LIGHTROOM_RELAY_PORT", 54399))
REPO_ROOT = Path(__file__).resolve().parents[1]
RELAY_LOG = Path(tempfile.gettempdir()) / "lightroom_relay.log"


def start_relay_process() -> None:
    """Start the relay detached from this process, so it outlives the session that started it"""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    kwargs: Dict[str, Any] = {"cwd": str(REPO_ROOT), "env": env, "stdin": subprocess.DEVNULL,
                              "stdout": subprocess.DEVNULL}
    log = open(RELAY_LOG, "a", encoding="utf-8")
    kwargs["stderr"] = log
    command = [sys.executable, "-m", "mcp_server.relay"]
    if sys.platform == "win32":
        base = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        try:
            # Leave the session's job object, if allowed, so closing the session doesn't kill it
            subprocess.Popen(command, creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB, **kwargs)
        except OSError:
            subprocess.Popen(command, creationflags=base, **kwargs)
    else:
        subprocess.Popen(command, start_new_session=True, **kwargs)
    log.close()
    logger.info(f"Started the Lightroom relay (log: {RELAY_LOG})")


class RelayBridge(SocketBridge):
    """SocketBridge that goes through the shared relay instead of straight to the plugin"""

    def __init__(self, host: str = RELAY_HOST, port: Optional[int] = None, auto_start: bool = True):
        super().__init__(host)
        self.port = port or RELAY_PORT
        self.auto_start = auto_start

    async def connect(self, retry_attempts: int = 5, retry_delay: float = 0.5) -> None:
        from .exceptions import ConnectionError as LRConnectionError
        started = False
        # A freshly started relay needs a moment (Python start-up) before it listens
        for attempt in range(retry_attempts + 6):
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                break
            except OSError:
                if self.auto_start and not started:
                    start_relay_process()
                    started = True
                elif not self.auto_start and attempt >= retry_attempts:
                    raise LRConnectionError(f"No Lightroom relay on {self.host}:{self.port}")
                await asyncio.sleep(retry_delay)
        else:
            raise LRConnectionError(f"Could not reach the Lightroom relay (log: {RELAY_LOG})")
        # One socket both ways: SocketBridge's send/receive code works unchanged
        self._send_writer = writer
        self._receive_writer = writer
        self._receive_reader = reader
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())

    def _request_extras(self, timeout: float) -> Dict[str, Any]:
        return {"timeout": timeout}

    def _wait_timeout(self, timeout: float) -> float:
        # The relay times the Lightroom call out itself; leave it room to report that
        return timeout + 5

    def _check_response(self, response: Dict[str, Any]) -> None:
        from .exceptions import ConnectionError as LRConnectionError
        error = response.get("error") or {}
        if not response.get("success") and error.get("code") == "LIGHTROOM_UNREACHABLE":
            unreachable = LRConnectionError(error.get("message", "Lightroom isn't reachable"),
                                            code="LIGHTROOM_UNREACHABLE")
            unreachable.sent = False
            raise unreachable
