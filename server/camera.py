"""Camera control module – wraps gphoto2 CLI for Canon DSLR capture."""

import logging
import os
import subprocess
import threading
from datetime import datetime
from typing import Optional

from server.config import CAPTURE_TARGET, PHOTO_DIR

logger = logging.getLogger(__name__)

# Serialisiert JEDEN gphoto2-Zugriff (Aufnahme, Display-Off, Akku-Status).
# Grund: Läuft ein Hintergrund-Thread (z. B. disable_display) noch im
# USB-Transfer und die nächste Aufnahme macht ein ``pkill gphoto2``, killt
# das den Transfer mitten drin → die Kamera-USB-Verbindung blockiert und die
# nächste Aufnahme hängt bis zum Timeout. Der Lock stellt sicher, dass nie
# zwei gphoto2-Operationen gleichzeitig laufen und ein pkill nur dann passiert,
# wenn garantiert keine eigene gphoto2-Operation aktiv ist.
_camera_lock = threading.RLock()


def ensure_photo_dir() -> str:
    """Create the photo directory if it does not exist and return its path."""
    os.makedirs(PHOTO_DIR, exist_ok=True)
    return PHOTO_DIR


def disable_display() -> None:
    """Turn off the camera's rear LCD while tethered over USB.

    Mirrors the approach used by self-o-mat (xtech/self-o-mat,
    ``GphotoCamera.cpp``): it sets the camera's ``viewfinder`` action to 1.
    On Canon EOS this engages the "Canon EOS Viewfinder" (live view is routed
    over USB), which switches the camera's own rear display OFF. ``eosviewfinder``
    and ``output`` are tried as fallbacks for bodies that name the key
    differently.

    Kein eigenes ``pkill`` mehr (das war die Ursache der Race-Condition) – der
    Zugriff wird stattdessen über ``_camera_lock`` serialisiert. Komplett
    non-fatal: ohne Kamera/Unterstützung passiert einfach nichts.
    """
    # Auf den Lock warten, aber nicht ewig – eine laufende Aufnahme hat Vorrang.
    if not _camera_lock.acquire(timeout=20):
        logger.debug("disable_display: camera busy, skipping")
        return
    try:
        for cfg in ("viewfinder=1", "eosviewfinder=1", "output=Off"):
            try:
                r = subprocess.run(
                    ["gphoto2", "--set-config", cfg],
                    capture_output=True,
                    timeout=8,
                )
                if r.returncode == 0:
                    logger.info("Camera display disabled via --set-config %s", cfg)
                    return
            except FileNotFoundError:
                return  # gphoto2 not installed (dev machine)
            except subprocess.TimeoutExpired:
                logger.debug("gphoto2 --set-config %s timed out", cfg)
        logger.debug("Camera display could not be disabled (camera not connected yet?)")
    finally:
        _camera_lock.release()


def read_ac_power() -> Optional[bool]:
    """Return True if the camera reports external/USB power, False if on battery.

    Returns None when it can't be determined (no camera, key unsupported, or a
    capture is currently in progress). Never blocks a capture: if the camera is
    busy we simply skip this poll.
    """
    if not _camera_lock.acquire(blocking=False):
        return None  # Aufnahme läuft – diesen Poll überspringen
    try:
        try:
            r = subprocess.run(
                ["gphoto2", "--get-config", "acpower"],
                capture_output=True,
                text=True,
                timeout=6,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if r.returncode != 0:
            return None
        # gphoto2 gibt u. a. "Current: 1" (1 = AC/USB-Strom) oder "Current: On".
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("Current:"):
                val = line.split(":", 1)[1].strip().lower()
                return val in ("1", "on", "true", "ac", "yes")
        return None
    finally:
        _camera_lock.release()


def capture_image() -> str:
    """Trigger the camera, download the image, and return its file path.

    Uses ``gphoto2 --capture-image-and-download`` so the photo is saved
    directly on the Raspberry Pi (not on the camera's SD card).

    Returns:
        Absolute path of the saved JPEG file.

    Raises:
        RuntimeError: If gphoto2 fails.
    """
    photo_dir = ensure_photo_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"foto_{timestamp}.jpg"
    filepath = os.path.join(photo_dir, filename)

    cmd = ["gphoto2"]

    # Den gesamten Kamera-Zugriff serialisieren: wartet, bis ein evtl. noch
    # laufender disable_display-Thread fertig ist (kein pkill mitten im Transfer).
    with _camera_lock:
        # Verwaiste, EXTERNE gphoto2-Helfer (z. B. gvfs auf dem Desktop) lösen,
        # die den USB-Bus blockieren. Dank Lock läuft hier garantiert keine
        # eigene gphoto2-Operation, die wir killen könnten.
        try:
            subprocess.run(["pkill", "-f", "gphoto2"], capture_output=True, timeout=5)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # ZUERST die Konfiguration setzen (falls gewünscht)
        if CAPTURE_TARGET == 0:
            cmd += ["--set-config", "capturetarget=1"]

        # DANN erst das Bild aufnehmen und herunterladen
        cmd += [
            "--capture-image-and-download",
            "--filename", filepath,
            "--force-overwrite",
        ]

        logger.info("Running: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            logger.info("gphoto2 stdout: %s", result.stdout)
        except subprocess.CalledProcessError as exc:
            logger.error("gphoto2 failed: %s", exc.stderr)
            raise RuntimeError(f"Camera capture failed: {exc.stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("gphoto2 timed out after 30 seconds")
            raise RuntimeError("Camera capture timed out. Is the camera mounted by the OS?") from exc
        except FileNotFoundError:
            raise RuntimeError("gphoto2 is not installed or not in PATH")

        # Flush OS write-buffers to disk so the file is fully readable before
        # the photo_taken SSE event is emitted to the browser.
        with open(filepath, "rb") as fh:
            os.fsync(fh.fileno())

    logger.info("Photo saved: %s", filepath)

    # Die Aufnahme kann das Kamera-Display wieder eingeschaltet haben –
    # im Hintergrund erneut ausschalten (wartet via Lock, kein Kill-Risiko).
    threading.Thread(target=disable_display, daemon=True).start()

    return filepath
