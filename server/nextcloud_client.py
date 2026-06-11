"""Nextcloud API client for background uploading and link sharing."""

import logging
import os
import secrets
import string
import threading

from urllib.parse import quote

import requests

from server.config import (
    NEXTCLOUD_BASE_FOLDER,
    NEXTCLOUD_PASSWORD,
    NEXTCLOUD_TIMEOUT,
    NEXTCLOUD_URL,
    NEXTCLOUD_USERNAME,
    PHOTO_DIR,
)

logger = logging.getLogger(__name__)

# Der Basisordner muss nur einmal pro Prozess geprüft/angelegt werden.
_base_folder_ready = False
_base_folder_lock = threading.Lock()


def _auth() -> tuple[str, str]:
    return (NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)


def _get_webdav_url(path: str = "") -> str:
    """Konstruiert die WebDAV URL für Nextcloud."""
    base = f"{NEXTCLOUD_URL.rstrip('/')}/remote.php/dav/files/{quote(NEXTCLOUD_USERNAME)}"
    if path:
        if not path.startswith("/"):
            path = "/" + path
        base += quote(path)
    return base


def ensure_base_folder() -> bool:
    """Stellt sicher, dass der Basisordner in Nextcloud existiert (einmal pro Prozess)."""
    global _base_folder_ready
    with _base_folder_lock:
        if _base_folder_ready:
            return True
        url = _get_webdav_url(NEXTCLOUD_BASE_FOLDER)
        try:
            res = requests.request("PROPFIND", url, auth=_auth(), timeout=NEXTCLOUD_TIMEOUT)
            if res.status_code == 404:
                logger.info("Basisordner '%s' existiert nicht, wird erstellt...", NEXTCLOUD_BASE_FOLDER)
                mkcol = requests.request("MKCOL", url, auth=_auth(), timeout=NEXTCLOUD_TIMEOUT)
                if mkcol.status_code not in (201, 405):
                    logger.error("Basisordner konnte nicht erstellt werden: HTTP %s", mkcol.status_code)
                    return False
            elif res.status_code >= 400 and res.status_code != 405:
                logger.error("PROPFIND auf Basisordner fehlgeschlagen: HTTP %s", res.status_code)
                return False
        except requests.RequestException as exc:
            logger.error("Nextcloud nicht erreichbar: %s", exc)
            return False
        _base_folder_ready = True
        return True


def create_shared_folder(session_id: str) -> str:
    """Erstellt einen Session-Ordner und gibt den öffentlichen Share-Link zurück."""
    folder_path = f"{NEXTCLOUD_BASE_FOLDER}/{session_id}"
    url = _get_webdav_url(folder_path)

    try:
        res = requests.request("MKCOL", url, auth=_auth(), timeout=NEXTCLOUD_TIMEOUT)
        if res.status_code not in (201, 405):  # 201 Created, 405 = existiert schon
            logger.error("Fehler beim Erstellen des Nextcloud-Ordners: HTTP %s", res.status_code)
            return ""

        # Share Link via OCS API erstellen (Read-Only Public Link)
        ocs_url = f"{NEXTCLOUD_URL.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares"
        headers = {
            "OCS-APIRequest": "true",
            "Accept": "application/json",
        }
        payload = {
            "path": folder_path,
            "shareType": 3,   # 3 = Public Link
            "permissions": 1,  # 1 = Read Only
        }
        share_res = requests.post(
            ocs_url, auth=_auth(), headers=headers, data=payload, timeout=NEXTCLOUD_TIMEOUT
        )
        if share_res.status_code == 200:
            share_url = share_res.json()["ocs"]["data"]["url"]
            logger.info("Share-Link erfolgreich erstellt: %s", share_url)
            return share_url
        logger.error("Fehler beim Erstellen des Share-Links: HTTP %s", share_res.status_code)
        return ""
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.error("Nextcloud Share fehlgeschlagen: %s", exc)
        return ""


def _upload_worker(session_id: str, photos: list[str]) -> None:
    """Hintergrund-Job: Lädt die Bilder nach und nach hoch."""
    for photo in photos:
        local_path = os.path.join(PHOTO_DIR, photo)
        remote_path = f"{NEXTCLOUD_BASE_FOLDER}/{session_id}/{photo}"
        url = _get_webdav_url(remote_path)

        try:
            with open(local_path, "rb") as f:
                # Uploads dürfen länger dauern als API-Calls (große JPEGs,
                # langsames WLAN) – daher großzügigerer Timeout.
                res = requests.put(url, auth=_auth(), data=f, timeout=max(NEXTCLOUD_TIMEOUT, 120))
            if res.status_code in (201, 204):
                logger.info("Erfolgreich hochgeladen: %s", photo)
            else:
                logger.error("Upload-Fehler für %s: HTTP %s", photo, res.status_code)
        except (OSError, requests.RequestException) as exc:
            logger.error("Ausnahme beim Hochladen von %s: %s", photo, exc)


def process_nextcloud_upload(photos: list[str]) -> str:
    """
    Initiiert den Nextcloud-Workflow:
    Erstellt Ordner, holt den Link und startet den Upload im Hintergrund.

    Returns the public share URL, or "" if Nextcloud is unreachable.
    """
    if not (NEXTCLOUD_URL and NEXTCLOUD_USERNAME and NEXTCLOUD_PASSWORD):
        logger.error("Nextcloud-Zugangsdaten fehlen (FOTOBOX_NC_URL/_USER/_PASS)")
        return ""

    if not ensure_base_folder():
        return ""

    # Kurzer, nicht erratbarer Ordnername (CSPRNG).
    alphabet = string.ascii_lowercase + string.digits
    session_id = "".join(secrets.choice(alphabet) for _ in range(8))

    share_url = create_shared_folder(session_id)
    if not share_url:
        return ""

    # Upload-Prozess im Hintergrund starten (blockiert nicht das UI)
    threading.Thread(target=_upload_worker, args=(session_id, photos), daemon=True).start()

    return share_url
