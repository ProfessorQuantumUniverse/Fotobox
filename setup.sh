#!/usr/bin/env bash
# Fotobox – one-time system setup for Raspberry Pi
set -euo pipefail

echo "=== Fotobox Setup ==="

# System packages
sudo apt-get update
sudo apt-get install -y gphoto2 libgphoto2-dev python3-pip python3-venv

# Python virtual environment
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create photo directory
mkdir -p "${HOME}/photos"

# .env anlegen, falls noch keine existiert
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo ">> .env aus Vorlage erstellt – bitte anpassen!"
fi

# Ensure kiosk helper is executable
chmod +x "$SCRIPT_DIR/kiosk.sh"

# Install systemd services
sudo cp fotobox.service /etc/systemd/system/
sudo cp fotobox-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fotobox.service

echo ""
echo "Setup complete.  Start with:  sudo systemctl start fotobox"
echo ""
echo "Kiosk ohne Desktop (empfohlen auf dem Pi 3):"
echo "  1. raspi-config → System Options → Boot / Auto Login → Console Autologin"
echo "  2. sudo apt-get install -y xserver-xorg xinit chromium-browser"
echo "  3. sudo systemctl enable --now fotobox-kiosk.service"
