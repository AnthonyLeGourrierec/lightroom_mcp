"""
Resilient client management that handles connection resets gracefully.

The connection to Lightroom is made lazily on the first tool call and checked
before every call, so the server recovers on its own when Lightroom or the
bridge is restarted: the next call simply reconnects.
"""
import logging
import sys
from typing import Optional, Dict, Any
from lightroom_sdk import LightroomClient
from lightroom_sdk.exceptions import ConnectionError as LRConnectionError
import asyncio

# Log to stderr for STDIO compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Keep connection attempts short: a tool call should fail fast with a clear
# message rather than hang while Lightroom is closed.
CONNECT_ATTEMPTS = 3

NOT_REACHABLE_MESSAGE = (
    "Lightroom isn't reachable. Make sure Lightroom Classic is open. If it is, "
    "start the bridge with File > Plug-in Extras > Start Python Bridge, then try again."
)


class ResilientClientManager:
    """Manages the shared Lightroom client with automatic reconnection"""

    def __init__(self):
        self._client: Optional[LightroomClient] = None
        self._reconnect_lock = asyncio.Lock()

    async def get_client(self) -> LightroomClient:
        """Return a connected client, reconnecting if the previous one dropped"""
        async with self._reconnect_lock:
            if self._client and self._client.is_connected:
                return self._client

            if self._client:
                logger.info("Lightroom connection was lost - reconnecting")
                await self._discard(self._client)
                self._client = None

            client = LightroomClient()
            try:
                await client.connect(retry_attempts=CONNECT_ATTEMPTS)
            except Exception as e:
                logger.warning(f"Could not connect to Lightroom: {e}")
                await self._discard(client)
                raise LRConnectionError(NOT_REACHABLE_MESSAGE, code="CONNECTION_FAILED") from e

            self._client = client
            return client

    async def execute_with_retry(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Execute a command, reconnecting once if the connection had dropped.

        A command is only retried when it never reached Lightroom. If the
        connection drops after it was sent, it may already have been applied,
        so the error is reported instead of running it twice.
        """
        client = await self.get_client()
        try:
            return await client.execute_command(command, params, timeout)
        except LRConnectionError as e:
            if getattr(e, "sent", True):
                raise LRConnectionError(
                    f"Lost the connection to Lightroom while running '{command}'. "
                    "It may or may not have been applied; check the photo before retrying.",
                    code="CONNECTION_FAILED"
                ) from e
            logger.info(f"Connection dropped before '{command}' was sent - reconnecting")

        client = await self.get_client()
        return await client.execute_command(command, params, timeout)

    async def connect(self) -> None:
        """Initialize connection to Lightroom (errors are logged, not raised)"""
        try:
            await self.get_client()
            logger.info("Connected to Lightroom bridge")
        except Exception as e:
            logger.error(f"Failed to connect to Lightroom: {e}")

    async def disconnect(self) -> None:
        """Disconnect from Lightroom"""
        async with self._reconnect_lock:
            if self._client:
                await self._discard(self._client)
                logger.info("Disconnected from Lightroom bridge")
                self._client = None

    @staticmethod
    async def _discard(client: LightroomClient) -> None:
        try:
            await client.disconnect()
        except Exception as e:
            logger.debug(f"Error while closing old connection: {e}")


# Global resilient client manager instance
resilient_client_manager = ResilientClientManager()
