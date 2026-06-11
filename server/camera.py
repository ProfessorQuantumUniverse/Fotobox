"""Camera control module – wraps gphoto2 CLI for Canon DSLR capture."""

import logging
import os
import subprocess
import threading
from datetime import datetime

from server.config import CAPTURE_TARGET, PHOTO_DIR

logger = logging.getLogger(__name__)


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

    Completely non-fatal: if the camera isn't connected or doesn't support the
    config, the app just continues – no error is raised or logged loudly.
    """
    # The lingering gphoto2 helper holds the USB lock; clear it first.
    try:
        subprocess.run(["pkill", "-f", "gphoto2"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

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

    # Kill any lingering gphoto2 helper that would hold the USB lock.
    # Non-fatal: pkill may not exist (dev machines) or find no process.
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
    # im Hintergrund erneut ausschalten, ohne die UI zu verzögern.
    threading.Thread(target=disable_display, daemon=True).start()

    return filepath
