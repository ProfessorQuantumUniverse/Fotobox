#!/usr/bin/env bash
# Fotobox – start helper (server + Chromium kiosk)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

export FOTOBOX_PHOTO_DIR="${FOTOBOX_PHOTO_DIR:-/home/pi/photos}"
export FOTOBOX_HOST="${FOTOBOX_HOST:-0.0.0.0}"
export FOTOBOX_PORT="${FOTOBOX_PORT:-5000}"

python -m server.app &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${FOTOBOX_PORT}/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

chromium --kiosk --noerrdialogs --disable-infobars "http://localhost:${FOTOBOX_PORT}"
