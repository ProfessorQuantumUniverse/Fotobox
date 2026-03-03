"""Fotobox configuration constants."""

import os

# --- Serial (Arduino) ---
SERIAL_PORT = os.environ.get("FOTOBOX_SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.environ.get("FOTOBOX_SERIAL_BAUD", "9600"))

# --- Photo storage ---
PHOTO_DIR = os.environ.get("FOTOBOX_PHOTO_DIR", "/home/pi/photos")

# --- Web server ---
HOST = os.environ.get("FOTOBOX_HOST", "0.0.0.0")
PORT = int(os.environ.get("FOTOBOX_PORT", "5000"))

# --- Camera ---
CAPTURE_TARGET = 1  # 0 = camera SD, 1 = download to host

# --- Display ---
REVIEW_SECONDS = int(os.environ.get("FOTOBOX_REVIEW_SECONDS", "5"))
