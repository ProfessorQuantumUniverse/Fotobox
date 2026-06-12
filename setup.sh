#!/usr/bin/env bash
# Fotobox – one-time system setup for Raspberry Pi
set -euo pipefail

echo "=== Fotobox Setup ==="

# System packages (inkl. nackter X-Server + Chromium für den Kiosk ohne Desktop)
sudo apt-get update
sudo apt-get install -y gphoto2 libgphoto2-dev python3-pip python3-venv \
  xserver-xorg xinit x11-xserver-utils chromium-browser

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

# Kiosk-Boot OHNE Desktop einrichten.
#
# WICHTIG: Bootet der Pi in den Desktop (PIXEL/LXDE), besitzt dieser bereits
# Display :0 – der Kiosk-Dienst kann dann mit `xinit ... :0` KEINEN zweiten
# X-Server starten und crasht in einer Endlosschleife (man landet auf dem
# Desktop). Darum den Pi auf "Console Autologin" stellen und erst dann den
# Kiosk-Dienst aktivieren.
if command -v raspi-config >/dev/null 2>&1; then
  # B2 = Console Autologin (loggt den Pi-User auf tty1 ein, kein Desktop).
  sudo raspi-config nonint do_boot_behaviour B2 || \
    echo ">> Konnte Boot-Verhalten nicht automatisch setzen – bitte manuell: raspi-config → Console Autologin"
else
  echo ">> raspi-config nicht gefunden – Boot-Verhalten bitte manuell auf Console Autologin stellen."
fi
sudo systemctl enable fotobox-kiosk.service

# Passwortloses Herunterfahren für das Shutdown-Menü (5× Knopf drücken).
# Erlaubt der Fotobox NUR den Shutdown-Befehl – sonst nichts.
SUDO_USER_NAME="$(id -un)"
echo "${SUDO_USER_NAME} ALL=(root) NOPASSWD: /sbin/shutdown, /usr/sbin/shutdown" | \
  sudo tee /etc/sudoers.d/fotobox-shutdown >/dev/null
sudo chmod 0440 /etc/sudoers.d/fotobox-shutdown

echo ""
echo "Setup complete.  Start with:  sudo systemctl start fotobox"
echo ""
echo "Kiosk (Chromium ohne Desktop) ist eingerichtet und für den nächsten Boot"
echo "aktiviert. Nach 'sudo reboot' startet die Fotobox automatisch im Vollbild."
echo "Falls noch ein Desktop erscheint, prüfen:"
echo "  sudo raspi-config nonint get_boot_behaviour   # muss B2 ergeben"
echo "  journalctl -u fotobox-kiosk -b --no-pager | tail -30"
echo ""
echo "USB-Stick-Backup (headless: ohne Auto-Mount findet die Fotobox keinen Stick!):"
echo "  Einmalig einrichten:   sudo ./setup-usb-automount.sh"
echo "  Danach wird jeder eingesteckte Stick automatisch (mit fotobox-Rechten)"
echo "  nach /media/usb-<gerät> gemountet und alle Fotos dorthin gesichert."
echo ""
echo "WICHTIG – stromausfallfestes Booten (Stecker ziehen ohne Schaden):"
echo "  Root read-only machen, damit hartes Ausschalten die SD-Karte/Services"
echo "  nicht beschädigt:   sudo ./enable-readonly-fs.sh"
echo "  Danach IMMER einen USB-Stick stecken lassen – Fotos werden dorthin"
echo "  gesichert (lokale ~/photos überleben dann keinen Neustart)."
echo "  Sauberes Ausschalten geht jederzeit über das Shutdown-Menü"
echo "  (5× schnell den Knopf drücken)."
