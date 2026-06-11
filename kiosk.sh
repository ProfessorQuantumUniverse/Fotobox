#!/usr/bin/env bash
# Fotobox – Kiosk-Browser OHNE Desktop-Umgebung.
#
# Wird von xinit als X-Session gestartet (siehe fotobox-kiosk.service):
# statt des kompletten PIXEL/LXDE-Desktops läuft nur der nackte X-Server
# plus Chromium. Das spart auf einem Pi 3 ~150–250 MB RAM und mehrere
# Sekunden Bootzeit.
#
# Voraussetzung: Boot-Verhalten auf "Console" stellen (raspi-config →
# System Options → Boot / Auto Login → Console Autologin).
set -u

URL="${FOTOBOX_URL:-http://localhost:5000}"

# Bildschirmschoner & Energiesparen aus – das Display soll dauerhaft an sein.
xset s off
xset s noblank
xset -dpms || true

# Warten, bis der Fotobox-Server antwortet (max. 60 s).
for _ in $(seq 1 60); do
  if curl -fs "${URL}/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Chromium heißt je nach Raspberry-Pi-OS-Version anders.
BROWSER="$(command -v chromium-browser || command -v chromium)"

# Flags reduzieren RAM-/CPU-Verbrauch auf dem Pi 3:
#  --disk-cache-dir=/dev/null  : kein Disk-Cache (schont die SD-Karte)
#  --disable-features=...      : Übersetzer & Co. abschalten
#  --check-for-update-interval : Update-Checks praktisch deaktivieren
exec "$BROWSER" \
  --kiosk "$URL" \
  --noerrdialogs \
  --disable-infobars \
  --disable-session-crashed-bubble \
  --disable-restore-session-state \
  --disable-features=Translate,BackForwardCache \
  --disable-component-update \
  --check-for-update-interval=31536000 \
  --disk-cache-dir=/dev/null \
  --no-first-run \
  --fast --fast-start \
  --overscroll-history-navigation=0
