#!/usr/bin/env bash
# Fotobox – Update einspielen (wird von POST /system/update aufgerufen).
#
# Holt den neuesten Stand des aktuellen Branches, installiert Abhängigkeiten
# und macht alle Skripte wieder ausführbar. Den Neustart übernimmt danach der
# Server (sudo shutdown -r now). Manuell geht's natürlich auch:
#   ./update.sh && sudo reboot
#
set -euo pipefail
cd "$(dirname "$0")"

echo "== Fotobox-Update =="
git pull --ff-only

if [ -x venv/bin/pip ]; then
  venv/bin/pip install -r requirements.txt
fi

chmod +x kiosk.sh setup.sh update.sh \
  enable-readonly-fs.sh setup-usb-automount.sh 2>/dev/null || true

sync
echo "== Update fertig – Neustart folgt =="
