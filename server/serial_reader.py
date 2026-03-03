"""Serial reader module – listens for Arduino events over USB serial."""

import logging
import threading
from typing import Callable, Optional

import serial

from server.config import SERIAL_BAUD, SERIAL_PORT

logger = logging.getLogger(__name__)


class SerialReader:
    """Reads newline-delimited messages from the Arduino over serial.

    Parameters:
        port: Serial device path (e.g. ``/dev/ttyUSB0``).
        baud: Baud rate (default from config).
        on_message: Callback invoked with each stripped line received.
    """

    def __init__(
        self,
        port: str = SERIAL_PORT,
        baud: int = SERIAL_BAUD,
        on_message: Optional[Callable[[str], None]] = None,
    ):
        self.port = port
        self.baud = baud
        self.on_message = on_message
        self._connection: Optional[serial.Serial] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # -- public API ---------------------------------------------------------

    def start(self) -> None:
        """Open the serial port and start the reader thread."""
        if self._running:
            return
        try:
            self._connection = serial.Serial(self.port, self.baud, timeout=1)
        except serial.SerialException as exc:
            logger.error("Cannot open serial port %s: %s", self.port, exc)
            raise
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("Serial reader started on %s @ %d baud", self.port, self.baud)

    def stop(self) -> None:
        """Signal the reader thread to stop and close the connection."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        if self._connection is not None and self._connection.is_open:
            self._connection.close()
            self._connection = None
        logger.info("Serial reader stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # -- internal -----------------------------------------------------------

    def _read_loop(self) -> None:
        """Continuously read lines and dispatch them to the callback."""
        while self._running:
            try:
                if self._connection is None or not self._connection.is_open:
                    break
                raw = self._connection.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    logger.debug("Serial RX: %s", line)
                    if self.on_message:
                        self.on_message(line)
            except serial.SerialException as exc:
                logger.error("Serial read error: %s", exc)
                break
            except Exception:
                logger.exception("Unexpected error in serial reader")
                break
        self._running = False
