# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Konfiguration anpassen
```

System dependencies (Raspberry Pi only): `gphoto2 libgphoto2-dev`; for the desktop-less kiosk additionally `xserver-xorg xinit chromium-browser`.

## Common Commands

```bash
# Run server
source venv/bin/activate && python -m server.app

# Run all tests
source venv/bin/activate && pytest

# Run a single test file
pytest tests/test_camera.py

# Run a single test
pytest tests/test_app.py::TestRoutes::test_index -v
```

## Architecture

The system is a Flask web app that runs on a Raspberry Pi 3 and drives a kiosk display. The three main integration points are the Arduino (serial), the Canon DSLR (gphoto2 CLI), and the browser UI (SSE).

**Event flow:**
1. Arduino sends `button_pressed` or `countdown_complete` over USB serial → `SerialReader` reads it in a daemon thread → calls `_on_serial_message()` in `app.py`
2. `_on_serial_message` puts events into the global `event_queue` and triggers `capture_image()` on `countdown_complete`
3. The `/events` SSE endpoint streams everything from `event_queue` to the browser
4. `app.js` is a pure SSE-driven state machine: it switches between 5 screens (`idle`, `countdown`, `review`, `qr`, `error`) based on received events

**Security model:** All control endpoints (`/`, `/events`, `/trigger`, `/session/*`) are restricted to localhost via a `before_request` hook — guests connected to the hotspot only get `/download`, `/photos/*`, `/photos/preview/*`, `/static/*`, and `/status`. Override for development with `FOTOBOX_ALLOW_REMOTE_CONTROL=1`. Secrets (AP password, Nextcloud session IDs) come from the `secrets` module, not `random`.

**Performance model (Pi 3):**
- The kiosk browser runs **without a desktop environment** (`kiosk.sh` + `fotobox-kiosk.service` start Chromium directly via xinit).
- The review screen and guest gallery load downscaled previews (`server/previews.py`, cached in `PHOTO_DIR/.previews/`) instead of full DSLR JPEGs; originals are only used for downloads.
- The nmcli AP profile is created once and reused (`connection up`/`down` only); AP credentials are generated once per process and cached, so repeat sessions skip the expensive profile rewrite entirely.
- All UI animations use only `transform`/`opacity` (GPU compositing).

**Session & sharing:**
- Photos are tracked in `_session_photos` (in-memory list, protected by `_session_lock`)
- When the user taps "Fertig", `POST /session/finish` fires and starts one of two share flows controlled by `FOTOBOX_SHARE_MODE`:
  - `hotspot`: Brings up the WiFi AP via `nmcli` + serves a local `/download` gallery. Returns WiFi QR + URL QR (shown stacked as steps 1 and 2).
  - `nextcloud`: Uploads to Nextcloud via WebDAV (background thread), creates an OCS share link, returns a single download QR. Upload is async — the QR is shown before upload completes. On failure the session photos are restored and the endpoint returns 503.
- An empty session returns 400.

**Application factory:** `create_app()` in `app.py` is used by both tests and production startup. Tests use the shared fixtures in `tests/conftest.py` (`photo_dir`, `client`) which patch `PHOTO_DIR` everywhere and mock all hardware/network.

**Modules:**
- `server/config.py` — all config comes from env vars (via `.env` loaded by `python-dotenv`); Nextcloud credentials have **no defaults** and must be set in `.env`
- `server/camera.py` — wraps `gphoto2` CLI; kills any existing `gphoto2` process before each capture (non-fatal if `pkill` is missing)
- `server/serial_reader.py` — background thread; missing serial port is non-fatal (app runs without Arduino, use `POST /trigger` to simulate)
- `server/access_point.py` — wraps `nmcli` with profile reuse; requires `sudo` on the Pi
- `server/nextcloud_client.py` — WebDAV + OCS API; every request has a timeout; uploads happen in a daemon thread after the share link is already returned
- `server/previews.py` — cached downscaled previews via Pillow `draft()` decoding

## Configuration (via env vars or `.env` — see `.env.example` for the full list)

| Variable | Default | Purpose |
|---|---|---|
| `FOTOBOX_SHARE_MODE` | `nextcloud` | `hotspot` or `nextcloud` |
| `FOTOBOX_NC_URL` / `_USER` / `_PASS` | — (required for nextcloud mode) | Nextcloud access (use an app password) |
| `FOTOBOX_NC_FOLDER` | `Fotobox` | Base folder in Nextcloud |
| `FOTOBOX_NC_TIMEOUT` | `10` | Timeout (s) for Nextcloud API calls |
| `FOTOBOX_PHOTO_DIR` | `~/photos` | Local photo storage |
| `FOTOBOX_SERIAL_PORT` | `/dev/ttyUSB0` | Arduino serial device |
| `FOTOBOX_ALLOW_REMOTE_CONTROL` | `0` | Allow control endpoints from non-localhost (dev only) |
| `FOTOBOX_REVIEW_SECONDS` | `30` | Auto-reset of the review screen (0 = off) |
| `FOTOBOX_QR_TIMEOUT_SECONDS` | `120` | Auto-reset of the QR screen (0 = off) |
| `FOTOBOX_PREVIEW_MAX_SIZE` | `1280` | Max edge length of preview images |
| `FOTOBOX_USB_BACKUP` | `1` | Copy every captured photo to a mounted USB stick (0 = off) |
| `FOTOBOX_USB_MOUNT_ROOTS` | `/media:/mnt` | Colon-separated roots scanned for a mounted stick |
| `FOTOBOX_USB_BACKUP_SUBDIR` | `Fotobox` | Target folder on the stick |

**Shutdown & power resilience:** Pressing the physical button **5× quickly** (within 4 s) during the countdown opens a shutdown menu (`screen-shutdown`); confirming hits `POST /system/shutdown` (localhost-only) which tears down the AP, `sync`s, and runs `sudo shutdown` (passwordless sudoers rule installed by `setup.sh`). For unclean power-offs (yanking the plug), enable the read-only overlay filesystem via `raspi-config` so the SD card/services survive — `setup.sh` prints the steps. A frontend capture watchdog returns the UI to idle if a capture hangs without producing a photo or error.

## Dev without hardware

The `/trigger` endpoint simulates an Arduino button press: it emits `button_pressed` immediately and fires `countdown_complete` (with photo capture) after an 8-second `Timer`. Repeated triggers while one is pending return 409 (debounce). Use it to test the full UI flow without camera or Arduino attached.

Note: on macOS, port 5000 is occupied by AirPlay — run with `FOTOBOX_PORT=5050`.

## Git

Work happens on the `dev` branch; `main` is for releases.
