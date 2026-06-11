"""Watch the Ethernet link and react to plug/unplug events.

On Linux the carrier state of an interface is exposed at
``/sys/class/net/<iface>/carrier`` (1 = cable in & link up, 0 = down). We poll
it from a daemon thread – no extra dependencies, negligible CPU on a Pi 3.

Transitions drive two callbacks:
  * cable plugged in  → ``on_connect``  (the app starts a git self-update)
  * cable pulled out  → ``on_disconnect`` (the app cancels any running update)
"""

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def _read_carrier(iface: str) -> Optional[bool]:
    """Return True/False for the link state, or None if it can't be read."""
    path = f"/sys/class/net/{iface}/carrier"
    try:
        with open(path) as fh:
            return fh.read().strip() == "1"
    except (FileNotFoundError, OSError):
        # Interface absent (e.g. dev laptop) or operstate down/unknown.
        return None


class EthernetMonitor:
    """Poll an interface's carrier and fire callbacks on state changes."""

    def __init__(
        self,
        iface: str = "eth0",
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        poll_interval: float = 2.0,
        carrier_reader: Callable[[str], Optional[bool]] = _read_carrier,
    ):
        self.iface = iface
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.poll_interval = poll_interval
        self._read = carrier_reader
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # None = unknown yet; we don't fire on the very first reading so a box
        # that boots with the cable already in doesn't trigger spuriously.
        self._last_state: Optional[bool] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def state(self) -> Optional[bool]:
        return self._last_state

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Ethernet monitor started on %s", self.iface)

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval + 1)
            self._thread = None

    def poll_once(self) -> None:
        """Read the carrier once and fire callbacks on a transition.

        Exposed separately so tests can drive transitions deterministically.
        """
        current = self._read(self.iface)
        if current is None:
            return
        previous = self._last_state
        self._last_state = current
        if previous is None or previous == current:
            return
        if current:
            logger.info("Ethernet connected on %s", self.iface)
            if self.on_connect:
                self.on_connect()
        else:
            logger.info("Ethernet disconnected on %s", self.iface)
            if self.on_disconnect:
                self.on_disconnect()

    def _loop(self) -> None:
        while self._running:
            try:
                self.poll_once()
            except Exception:  # noqa: BLE001 – never let the monitor thread die
                logger.exception("Ethernet monitor poll failed")
            time.sleep(self.poll_interval)
