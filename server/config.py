"""Fotobox configuration constants."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


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

# --- Auto-Update über Ethernet ---
# Solange ein LAN-Kabel steckt, prüft die Box im festen Takt still im
# Hintergrund auf eine neuere Version (git) und zieht sie automatisch.
# Ein Toast erscheint NUR, wenn tatsächlich eine neue Version geladen wurde.
# Offline/ausgesteckt passiert nichts – keine Fehlermeldungen.
ETH_IFACE = os.environ.get("FOTOBOX_ETH_IFACE", "eth0")
AUTO_UPDATE = os.environ.get("FOTOBOX_AUTO_UPDATE", "1") == "1"
# Takt der Update-Prüfung in Sekunden (Default 10).
ETH_POLL_INTERVAL = float(os.environ.get("FOTOBOX_ETH_POLL_INTERVAL", "10"))

# --- Access Point ---
AP_IFACE = os.environ.get("FOTOBOX_AP_IFACE", "wlan0")
AP_CONNECTION_NAME = os.environ.get("FOTOBOX_AP_CONNECTION_NAME", "fotobox-ap")
AP_IP = os.environ.get("FOTOBOX_AP_IP", "10.42.0.1")
