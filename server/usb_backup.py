"""USB-Stick-Backup – kopiert jedes aufgenommene Foto auf einen Stick.

Steckt ein USB-Stick im Pi, wird JEDES Foto (auch die später nicht geteilten)
zusätzlich darauf gesichert. Komplett best-effort: ist kein Stick da oder
schlägt das Kopieren fehl, läuft die Fotobox unbeeinträchtigt weiter.
"""

import logging
import os
import shutil
import threading
from typing import Optional

from server.config import USB_BACKUP_SUBDIR, USB_MOUNT_ROOTS

logger = logging.getLogger(__name__)


def find_usb_mount(roots=USB_MOUNT_ROOTS) -> Optional[str]:
    """Return the path of the first writable, mounted USB stick, or ``None``.

    Deckt beide üblichen Raspberry-Pi-OS-Layouts ab:
    ``/media/<user>/<label>`` (Bookworm, automount) und ``/media/<label>`` bzw.
    ``/mnt/<label>`` (manuell). Nur echte Mountpoints, auf die wir schreiben
    dürfen, kommen in Frage.
    """
    for root in roots:
        if not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        for entry in entries:
            path = os.path.join(root, entry)
            # Direkter Mount (z. B. /media/USB) ODER eine Ebene tiefer
            # (z. B. /media/pi/USB).
            candidates = [path]
            if os.path.isdir(path):
                try:
                    candidates += [os.path.join(path, sub) for sub in sorted(os.listdir(path))]
                except OSError:
                    pass
            for candidate in candidates:
                if os.path.ismount(candidate) and os.access(candidate, os.W_OK):
                    return candidate
    return None


def backup_photo(filepath: str, mount: Optional[str] = None) -> Optional[str]:
    """Copy one photo to the USB stick if one is mounted. Best-effort.

    Returns the destination path on success, otherwise ``None``. Nach dem
    Kopieren wird ``fsync`` aufgerufen, damit ein ohne Auswerfen abgezogener
    Stick das Bild nicht verliert.
    """
    mount = mount or find_usb_mount()
    if not mount:
        return None
    try:
        dest_dir = os.path.join(mount, USB_BACKUP_SUBDIR)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(filepath))
        shutil.copy2(filepath, dest)
        with open(dest, "rb") as fh:
            os.fsync(fh.fileno())
        logger.info("Photo backed up to USB: %s", dest)
        return dest
    except OSError as exc:
        logger.warning("USB backup failed for %s: %s", filepath, exc)
        return None


def backup_photo_async(filepath: str) -> None:
    """Fire-and-forget USB-Backup in einem Daemon-Thread (blockiert nie)."""
    threading.Thread(target=backup_photo, args=(filepath,), daemon=True).start()
