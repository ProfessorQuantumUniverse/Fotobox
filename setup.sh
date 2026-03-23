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
mkdir -p /home/pi/photos

# Ensure start helper is executable
chmod +x "$SCRIPT_DIR/start.sh"

# Install systemd service
sudo cp fotobox.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fotobox.service

echo ""
echo "Setup complete.  Start with:  sudo systemctl start fotobox"
