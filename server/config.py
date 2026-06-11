"""Fotobox configuration constants."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# --- Sharing Mode ---
# "hotspot" (lokales WLAN) oder "nextcloud" (Cloud Upload)
SHARE_MODE = os.environ.get("FOTOBOX_SHARE_MODE", "nextcloud").lower()
if SHARE_MODE not in ("hotspot", "nextcloud"):
    logger.warning("Unknown FOTOBOX_SHARE_MODE=%r, falling back to 'hotspot'", SHARE_MODE)
    SHARE_MODE = "hotspot"

# --- Nextcloud Settings ---
# Keine Defaults für URL/Credentials: die gehören in die .env-Datei
# (App-Passwort verwenden: Nextcloud > Sicherheit > Geräte & Sitzungen).
NEXTCLOUD_URL = os.environ.get("FOTOBOX_NC_URL", "")
NEXTCLOUD_USERNAME = os.environ.get("FOTOBOX_NC_USER", "")
NEXTCLOUD_PASSWORD = os.environ.get("FOTOBOX_NC_PASS", "")
NEXTCLOUD_BASE_FOLDER = os.environ.get("FOTOBOX_NC_FOLDER", "Fotobox")
# Timeout für alle Nextcloud-HTTP-Requests (Sekunden) – verhindert, dass die
# UI hängt, wenn die Cloud nicht erreichbar ist.
NEXTCLOUD_TIMEOUT = int(os.environ.get("FOTOBOX_NC_TIMEOUT", "10"))

if SHARE_MODE == "nextcloud" and not (NEXTCLOUD_URL and NEXTCLOUD_USERNAME and NEXTCLOUD_PASSWORD):
    logger.warning(
        "FOTOBOX_SHARE_MODE=nextcloud, aber FOTOBOX_NC_URL/_USER/_PASS sind nicht "
        "vollständig gesetzt – Uploads werden fehlschlagen."
    )

# --- Serial (Arduino) ---
SERIAL_PORT = os.environ.get("FOTOBOX_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.environ.get("FOTOBOX_SERIAL_BAUD", "9600"))

PHOTO_DIR = os.path.abspath(os.environ.get("FOTOBOX_PHOTO_DIR", os.path.expanduser("~/photos")))

# --- Web server ---
HOST = os.environ.get("FOTOBOX_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOTOBOX_PORT", "5000"))

# Kontroll-Endpoints (Kiosk-UI, Trigger, Session-Verwaltung) sind standardmäßig
# nur von localhost erreichbar. Gäste im Hotspot bekommen nur /download und
# /photos. Zum Entwickeln von einem anderen Rechner: FOTOBOX_ALLOW_REMOTE_CONTROL=1
ALLOW_REMOTE_CONTROL = os.environ.get("FOTOBOX_ALLOW_REMOTE_CONTROL", "0") == "1"

# --- Camera ---
CAPTURE_TARGET = 1  # 0 = camera SD, 1 = download to host

# --- Display ---
# Wie lange das Review unangetastet stehen bleibt, bevor die Box automatisch
# zurück zum Idle-Screen geht (Foto bleibt in der Session).
REVIEW_SECONDS = int(os.environ.get("FOTOBOX_REVIEW_SECONDS", "30"))
# Auto-Reset des QR-Screens, falls niemand "Neue Session" drückt.
QR_TIMEOUT_SECONDS = int(os.environ.get("FOTOBOX_QR_TIMEOUT_SECONDS", "120"))

# --- Previews ---
# Maximale Kantenlänge der downskalierten Vorschau-Bilder. Volle DSLR-JPEGs
# (20+ MP) bringen den Chromium auf dem Pi 3 ans Limit – die Preview nicht.
PREVIEW_MAX_SIZE = int(os.environ.get("FOTOBOX_PREVIEW_MAX_SIZE", "1280"))

# --- Access Point ---
AP_IFACE = os.environ.get("FOTOBOX_AP_IFACE", "wlan0")
AP_CONNECTION_NAME = os.environ.get("FOTOBOX_AP_CONNECTION_NAME", "fotobox-ap")
AP_IP = os.environ.get("FOTOBOX_AP_IP", "10.42.0.1")
