"""Nextcloud API client for background uploading and link sharing."""

import logging
import os
import random
import string
import threading
from urllib.parse import quote

import requests

from server.config import (
    NEXTCLOUD_BASE_FOLDER,
    NEXTCLOUD_PASSWORD,
    NEXTCLOUD_URL,
    NEXTCLOUD_USERNAME,
    PHOTO_DIR,
)

logger = logging.getLogger(__name__)


def _get_webdav_url(path: str = "") -> str:
    """Konstruiert die WebDAV URL für Nextcloud."""
    # Nextcloud WebDAV Base URL
    base = f"{NEXTCLOUD_URL.rstrip('/')}/remote.php/dav/files/{NEXTCLOUD_USERNAME}"
    if path:
        if not path.startswith("/"):
            path = "/" + path
        base += quote(path)
    return base


def ensure_base_folder() -> None:
    """Stellt sicher, dass der Basisordner 'Fotobox' in Nextcloud existiert."""
    url = _get_webdav_url(NEXTCLOUD_BASE_FOLDER)
    auth = (NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)
    res = requests.request("PROPFIND", url, auth=auth)
    
    if res.status_code == 404:
        logger.info("Basisordner '%s' existiert nicht, wird erstellt...", NEXTCLOUD_BASE_FOLDER)
        requests.request("MKCOL", url, auth=auth)


def create_shared_folder(session_id: str) -> str:
    """Erstellt einen Session-Ordner und gibt den öffentlichen Share-Link zurück."""
    folder_path = f"{NEXTCLOUD_BASE_FOLDER}/{session_id}"
    url = _get_webdav_url(folder_path)
    auth = (NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)

    # Ordner erstellen
    res = requests.request("MKCOL", url, auth=auth)
    if res.status_code not in (201, 405):  # 201 Created, 405 Method Not Allowed (existiert schon)
        logger.error("Fehler beim Erstellen des Nextcloud-Ordners: %s", res.text)
        return ""

    # Share Link via OCS API erstellen
    ocs_url = f"{NEXTCLOUD_URL.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }
    payload = {
        "path": folder_path,
        "shareType": 3,  # 3 = Public Link
        "permissions": 1 # 1 = Read Only
    }
    
    share_res = requests.post(ocs_url, auth=auth, headers=headers, data=payload)
    if share_res.status_code == 200:
        data = share_res.json()
        share_url = data["ocs"]["data"]["url"]
        logger.info("Share-Link erfolgreich erstellt: %s", share_url)
        return share_url
    else:
        logger.error("Fehler beim Erstellen des Share-Links: %s", share_res.text)
        return ""


def _upload_worker(session_id: str, photos: list[str]) -> None:
    """Hintergrund-Job: Lädt die Bilder nach und nach hoch."""
    auth = (NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)
    for photo in photos:
        local_path = os.path.join(PHOTO_DIR, photo)
        remote_path = f"{NEXTCLOUD_BASE_FOLDER}/{session_id}/{photo}"
        url = _get_webdav_url(remote_path)
        
        try:
            with open(local_path, "rb") as f:
                res = requests.put(url, auth=auth, data=f)
                if res.status_code in (201, 204):
                    logger.info("Erfolgreich hochgeladen: %s", photo)
                else:
                    logger.error("Upload-Fehler für %s: HTTP %s", photo, res.status_code)
        except Exception as exc:
            logger.error("Ausnahme beim Hochladen von %s: %s", photo, exc)


def process_nextcloud_upload(photos: list[str]) -> str:
    """
    Initiiert den Nextcloud-Workflow:
    Erstellt Ordner, holt den Link und startet den Upload im Hintergrund.
    """
    ensure_base_folder()
    
    # Einen kurzen, eindeutigen Ordnernamen generieren
    session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    # Link sofort generieren
    share_url = create_shared_folder(session_id)
    
    # Upload-Prozess im Hintergrund starten (blockiert nicht das UI)
    threading.Thread(target=_upload_worker, args=(session_id, photos), daemon=True).start()
    
    return share_url
