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
- `server/updater.py` — manual update offer: overlay detection, `git fetch` check, `update.sh` runner, reboot
- `server/usb_backup.py` — copies photos to a mounted USB stick; a poll loop in `app.py` toasts on insert/removal and bulk-backs-up on insert. **A headless Pi has no automounter**, so a stick sits unmounted and is never found. Run `sudo ./setup-usb-automount.sh` once: it installs a udev rule + systemd templates that auto-mount any inserted stick to `/media/usb-<dev>` **with `fotobox` ownership** (the detection in `find_usb_mount` requires write access — a plain root `mount` fails `os.access(W_OK)` and produces no toast). Handles vfat/exFAT/NTFS/ext4.

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
| `FOTOBOX_UPDATE_PIN` | `5050` | PIN for installing offered updates at the kiosk |
| `FOTOBOX_UPDATE_CHECK_INTERVAL` | `300` | Seconds between update checks (`git fetch`), 0 = off |

**Shutdown & power resilience:** Pressing the physical button **5× quickly** (within 4 s) during the countdown opens a shutdown menu (`screen-shutdown`); confirming hits `POST /system/shutdown` (localhost-only) which tears down the AP, `sync`s, and runs `sudo shutdown` (passwordless sudoers rule installed by `setup.sh`). The Arduino firmware (`arduino/fotobox_trigger`) detects the 5-tap burst itself: `runCountdown()` polls the button via `interruptibleDelay()` and **aborts the capture** (no `countdown_complete`, no flash, no photo) once the threshold is hit. For unclean power-offs (yanking the plug), run `sudo ./enable-readonly-fs.sh` to put the root filesystem on a read-only overlay so the SD card/services survive — photos then live only on the USB stick. A frontend capture watchdog returns the UI to idle if a capture hangs without producing a photo or error.

**Updates (offered, never automatic):** A background loop (`_update_check_loop`) runs `git fetch` every `FOTOBOX_UPDATE_CHECK_INTERVAL` seconds; if the remote is ahead, the UI shows a **persistent, tappable toast** (no timeout — it goes away only when tapped, or when a photo session starts). Tapping it opens an on-screen PIN pad (`FOTOBOX_UPDATE_PIN`, default `5050`); the correct PIN hits `POST /system/update` (localhost-only, `hmac.compare_digest`) which runs `update.sh` (git pull --ff-only, pip install, re-chmod scripts) and reboots via the existing `sudo shutdown -r` sudoers rule. If the read-only overlay is active (`server/updater.py:is_overlay_root`), the endpoint refuses with 409 since the update wouldn't survive a reboot.

**Idle-screen input:** Tapping anywhere on the idle screen triggers a photo (`POST /trigger`) — EXCEPT the top-right third (x > ⅔·width, y < ⅓·height): 5 taps there within 4 s open the shutdown menu and single taps there never trigger a photo. `index.html` loads `app.js`/`style.css` with `?v=<server-start-time>` so the kiosk browser never runs stale assets after a deploy (assets are otherwise cached 1 h).

## Dev without hardware

The `/trigger` endpoint simulates an Arduino button press: it emits `button_pressed` immediately and fires `countdown_complete` (with photo capture) after an 8-second `Timer`. Repeated triggers while one is pending return 409 (debounce). Use it to test the full UI flow without camera or Arduino attached.

Note: on macOS, port 5000 is occupied by AirPlay — run with `FOTOBOX_PORT=5050`.

## Git

Work happens on the `dev` branch; `main` is for releases.
