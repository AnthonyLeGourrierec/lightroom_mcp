import asyncio
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from asyncio import StreamReader, StreamWriter

logger = logging.getLogger(__name__)

# Written by the Lua plugin (on Windows this resolves to C:\tmp\lightroom_ports.txt)
DEFAULT_PORT_FILE = '/tmp/lightroom_ports.txt'

class SocketBridge:
    """Manages dual socket connections to Lightroom plugin"""

    def __init__(self, host: str = '127.0.0.1', port_file: Optional[str] = None):
        self.host = host
        self.port_file = Path(port_file or DEFAULT_PORT_FILE)
        self._send_writer: Optional[StreamWriter] = None
        self._receive_reader: Optional[StreamReader] = None
        # Keep the receive connection's writer alive: on Python 3.11+ a
        # garbage-collected StreamWriter closes its transport immediately.
        self._receive_writer: Optional[StreamWriter] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._receive_task: Optional[asyncio.Task] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """True while the connection is up (cleared as soon as Lightroom closes it)"""
        return self._connected

    async def connect(self, retry_attempts: int = 5, retry_delay: float = 0.5) -> None:
        """Establish connection with exponential backoff and port file monitoring"""
        port_file_notified = False

        for attempt in range(retry_attempts):
            try:
                await self._close_streams()
                ports = await self._read_ports()
                if not ports:
                    if not port_file_notified:
                        logger.info(f"Waiting for Lightroom plugin to start...")
                        logger.info(f"Port file not found at {self.port_file}")
                        logger.info("Please ensure:")
                        logger.info("  1. Lightroom Classic is running")
                        logger.info("  2. lightroom-python-bridge.lrdevplugin is installed and active")
                        logger.info("  3. Plugin has started successfully")
                        port_file_notified = True
                    
                    # Wait for port file to appear with polling
                    await self._wait_for_port_file(timeout=retry_delay * (2 ** attempt))
                    ports = await self._read_ports()
                    
                    if not ports:
                        from .exceptions import ConnectionError as LRConnectionError
                        raise LRConnectionError("Port file still not available")

                sender_port, receiver_port = ports
                logger.info(f"Found Lightroom bridge ports: {sender_port}, {receiver_port}")

                # Connect to Lightroom's receiver (where we send)
                _, self._send_writer = await asyncio.open_connection(
                    self.host, receiver_port
                )

                # Connect to Lightroom's sender (where we receive)
                self._receive_reader, self._receive_writer = await asyncio.open_connection(
                    self.host, sender_port
                )

                self._connected = True
                self._receive_task = asyncio.create_task(self._receive_loop())
                logger.info(f"✅ Connected to Lightroom bridge successfully!")
                return

            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1}/{retry_attempts} failed: {e}")
                if attempt < retry_attempts - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                else:
                    from .exceptions import ConnectionError as LRConnectionError
                    error_msg = (
                        f"Failed to connect to Lightroom after {retry_attempts} attempts. "
                        f"Please ensure Lightroom Classic is running with the plugin active."
                    )
                    raise LRConnectionError(error_msg)

    async def _wait_for_port_file(self, timeout: float = 10.0, poll_interval: float = 0.5) -> None:
        """Wait for port file to appear with polling"""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            if self.port_file.exists():
                logger.info(f"✅ Port file appeared at {self.port_file}")
                return
            await asyncio.sleep(poll_interval)
        
        logger.warning(f"Port file did not appear within {timeout:.1f} seconds")

    async def _read_ports(self) -> Optional[Tuple[int, int]]:
        """Read port numbers from Lightroom's port file"""
        if not self.port_file.exists():
            return None

        try:
            content = self.port_file.read_text().strip()
            ports = content.split(',')
            return int(ports[0]), int(ports[1])
        except Exception as e:
            logger.error(f"Failed to read port file: {e}")
            return None

    async def _receive_loop(self) -> None:
        """Background task to receive messages from Lightroom"""
        buffer = b""
        while self._connected:
            try:
                chunk = await self._receive_reader.read(8192)
                if not chunk:
                    logger.warning("Connection closed by Lightroom")
                    break

                buffer += chunk

                # Process complete messages
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    try:
                        message = json.loads(line.decode('utf-8'))
                        await self._handle_message(message)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON received: {e}")

            except Exception as e:
                logger.error(f"Receive loop error: {e}")
                break

        self._connected = False
        self._fail_pending("Lightroom closed the connection")

    def _fail_pending(self, reason: str) -> None:
        """Fail every command still waiting for a reply, instead of letting each time out"""
        from .exceptions import ConnectionError as LRConnectionError
        pending, self._pending_requests = self._pending_requests, {}
        for future in pending.values():
            if not future.done():
                error = LRConnectionError(reason)
                error.sent = True
                future.set_exception(error)

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Route received messages to appropriate handlers"""
        # Handle events
        if 'event' in message:
            logger.debug(f"Event received: {message['event']}")
            # TODO: Implement event handling
            return

        # Handle responses
        request_id = message.get('id')
        if request_id and request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.cancelled():
                future.set_result(message)

    async def send_command(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Send command and await response"""
        from .exceptions import ConnectionError as LRConnectionError
        if not self._connected:
            error = LRConnectionError("Not connected to Lightroom")
            error.sent = False
            raise error

        request_id = str(uuid.uuid4())
        request = {
            'id': request_id,
            'command': command,
            'params': params or {},
            **self._request_extras(timeout)
        }

        # Create future for response
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            # Send request
            request_json = json.dumps(request) + '\n'
            try:
                self._send_writer.write(request_json.encode('utf-8'))
                await self._send_writer.drain()
            except OSError as e:
                # The write itself failed, so Lightroom never got the command
                self._connected = False
                error = LRConnectionError(f"Connection to Lightroom lost: {e}")
                error.sent = False
                raise error from e

            # Wait for response
            response = await asyncio.wait_for(future, timeout=self._wait_timeout(timeout))
            self._check_response(response)
            return response

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            from .exceptions import TimeoutError as LRTimeoutError
            raise LRTimeoutError(f"Command '{command}' timed out after {timeout}s")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise

    # Hooks for RelayBridge
    def _request_extras(self, timeout: float) -> Dict[str, Any]:
        return {}

    def _wait_timeout(self, timeout: float) -> float:
        return timeout

    def _check_response(self, response: Dict[str, Any]) -> None:
        pass

    async def disconnect(self) -> None:
        """Close connections gracefully"""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        await self._close_streams()
        self._fail_pending("Disconnected from Lightroom")
        logger.info("Disconnected from Lightroom bridge")

    async def _close_streams(self) -> None:
        """Close any open sockets, ignoring errors from ones already dead"""
        for writer in (self._send_writer, self._receive_writer):
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
        self._send_writer = None
        self._receive_writer = None
        self._receive_reader = None