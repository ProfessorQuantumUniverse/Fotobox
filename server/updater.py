"""Manuelle Updates – prüfen, anbieten, auf Knopfdruck installieren.

Kein Auto-Update: Die Box prüft nur im Hintergrund, ob das Git-Remote neuere
Commits hat, und meldet das der UI. Installiert wird erst, wenn jemand am
Kiosk die Update-Toast antippt und die PIN eingibt (POST /system/update).
Auf einem Read-Only-Overlay (enable-readonly-fs.sh) wird das Update
verweigert, weil es einen Neustart nicht überleben würde.
"""

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Projekt-Wurzel (= Git-Repo): server/updater.py -> server -> Repo.
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

UPDATE_SCRIPT = os.path.join(REPO_DIR, "update.sh")


def is_overlay_root() -> bool:
    """True, wenn '/' auf einem Overlay-Dateisystem liegt (Read-Only-Modus).

    Dann gehen alle Schreibzugriffe nur ins RAM und ein Update wäre nach dem
    nächsten Neustart wieder verschwunden.
    """
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 3 and parts[1] == "/" and parts[2] == "overlay":
                    return True
    except OSError:
        pass
    return False


def check_for_update() -> Optional[dict]:
    """``git fetch`` und zählen, wie viele Commits das Remote voraus ist.

    Gibt ``{"behind": n}`` zurück, wenn es etwas zu installieren gibt, sonst
    ``None``. Komplett best-effort: ohne Netz/Remote einfach ``None``.
    """
    try:
        subprocess.run(
            ["git", "fetch", "--quiet"],
            cwd=REPO_DIR, timeout=30, check=True, capture_output=True,
        )
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..@{upstream}"],
            cwd=REPO_DIR, timeout=10, check=True, capture_output=True, text=True,
        )
        behind = int(result.stdout.strip())
        return {"behind": behind} if behind > 0 else None
    except Exception:
        return None


def run_update_script() -> None:
    """Führt update.sh aus (git pull, pip install, Skripte). Wirft bei Fehlern."""
    result = subprocess.run(
        ["bash", UPDATE_SCRIPT],
        cwd=REPO_DIR, timeout=600, capture_output=True, text=True,
    )
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-400:]
        raise RuntimeError(f"update.sh fehlgeschlagen: {tail}")


def reboot() -> None:
    """Neustart über die bestehende sudoers-Regel (shutdown ist erlaubt)."""
    subprocess.run(["sync"], timeout=10)
    subprocess.run(["sudo", "shutdown", "-r", "now"], timeout=10)
