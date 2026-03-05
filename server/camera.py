"""Camera control module – wraps gphoto2 CLI for Canon DSLR capture."""

import logging
import os
import subprocess
from datetime import datetime

from server.config import CAPTURE_TARGET, PHOTO_DIR

logger = logging.getLogger(__name__)


def ensure_photo_dir() -> str:
    """Create the photo directory if it does not exist and return its path."""
    os.makedirs(PHOTO_DIR, exist_ok=True)
    return PHOTO_DIR


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
    except FileNotFoundError:
        raise RuntimeError("gphoto2 is not installed or not in PATH")

    if not os.path.isfile(filepath):
        raise RuntimeError(f"Photo file not found after capture: {filepath}")

    # Flush OS write-buffers to disk so the file is fully readable before
    # the photo_taken SSE event is emitted to the browser.
    with open(filepath, "rb") as fh:
        os.fsync(fh.fileno())

    logger.info("Photo saved: %s", filepath)
    return filepath
