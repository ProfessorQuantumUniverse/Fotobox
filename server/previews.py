"""Downscaled photo previews for the kiosk UI and download gallery.

A Canon DSLR JPEG is 20+ megapixels – decoding that in Chromium on a
Raspberry Pi 3 takes seconds and hundreds of MB of RAM. The kiosk review
screen and the guest gallery therefore use cached previews capped at
``PREVIEW_MAX_SIZE`` pixels. Pillow's ``draft()`` mode lets libjpeg decode
directly at a reduced scale, so generating the preview is cheap even on
the Pi itself. Full-resolution originals stay available for download.
"""

import logging
import os
import threading

from PIL import Image

from server.config import PHOTO_DIR, PREVIEW_MAX_SIZE

logger = logging.getLogger(__name__)

PREVIEW_DIRNAME = ".previews"

_generate_lock = threading.Lock()


def preview_dir() -> str:
    return os.path.join(PHOTO_DIR, PREVIEW_DIRNAME)


def get_or_create_preview(filename: str) -> str | None:
    """Return the path of the cached preview for ``filename``.

    Generates the preview on first access. Returns ``None`` if the source
    photo does not exist or cannot be decoded.
    """
    # send_from_directory already blocks traversal for serving, but we build
    # paths ourselves here – reject anything that is not a bare filename.
    if os.path.basename(filename) != filename or filename.startswith("."):
        return None

    source = os.path.join(PHOTO_DIR, filename)
    if not os.path.isfile(source):
        return None

    target = os.path.join(preview_dir(), filename)
    if os.path.isfile(target) and os.path.getmtime(target) >= os.path.getmtime(source):
        return target

    # Serialise generation: parallel requests for the same fresh photo would
    # otherwise decode the full JPEG twice on a Pi 3.
    with _generate_lock:
        if os.path.isfile(target) and os.path.getmtime(target) >= os.path.getmtime(source):
            return target
        try:
            os.makedirs(preview_dir(), exist_ok=True)
            with Image.open(source) as img:
                img.draft("RGB", (PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
                img.thumbnail((PREVIEW_MAX_SIZE, PREVIEW_MAX_SIZE))
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                img.save(target, format="JPEG", quality=82, optimize=True)
        except (OSError, ValueError) as exc:
            logger.error("Preview generation failed for %s: %s", filename, exc)
            return None

    return target


def warm_preview_async(filename: str) -> None:
    """Generate the preview in a background thread (fire-and-forget).

    Called right after capture so the review screen hits a warm cache.
    """
    threading.Thread(target=get_or_create_preview, args=(filename,), daemon=True).start()
