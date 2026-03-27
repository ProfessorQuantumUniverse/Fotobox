"""Fotobox configuration constants."""

import os

# --- Sharing Mode ---
# "hotspot" (lokales WLAN) oder "nextcloud" (Cloud Upload)
SHARE_MODE = os.environ.get("FOTOBOX_SHARE_MODE", "nextcloud").lower()

# --- Nextcloud Settings ---
NEXTCLOUD_URL = os.environ.get("FOTOBOX_NC_URL", "https://technik.waldorfschule-frankfurt.de/cloud")
# Erstelle dir in Nextcloud am besten ein "App-Passwort" für die Fotobox (Sicherheit > Geräte & Sitzungen)
NEXTCLOUD_USERNAME = os.environ.get("FOTOBOX_NC_USER", "dein_nextcloud_benutzername")
NEXTCLOUD_PASSWORD = os.environ.get("FOTOBOX_NC_PASS", "dein_nextcloud_app_passwort")
NEXTCLOUD_BASE_FOLDER = os.environ.get("FOTOBOX_NC_FOLDER", "Fotobox")

# --- Serial (Arduino) ---
SERIAL_PORT = os.environ.get("FOTOBOX_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.environ.get("FOTOBOX_SERIAL_BAUD", "9600"))

PHOTO_DIR = os.path.abspath(os.environ.get("FOTOBOX_PHOTO_DIR", os.path.expanduser("~/photos")))

# --- Web server ---
HOST = os.environ.get("FOTOBOX_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOTOBOX_PORT", "5000"))

# --- Camera ---
CAPTURE_TARGET = 1  # 0 = camera SD, 1 = download to host

# --- Display ---
REVIEW_SECONDS = int(os.environ.get("FOTOBOX_REVIEW_SECONDS", "5"))

# --- Access Point ---
AP_IFACE = os.environ.get("FOTOBOX_AP_IFACE", "wlan0")
AP_CONNECTION_NAME = os.environ.get("FOTOBOX_AP_CONNECTION_NAME", "fotobox-ap")
AP_IP = os.environ.get("FOTOBOX_AP_IP", "10.42.0.1")
