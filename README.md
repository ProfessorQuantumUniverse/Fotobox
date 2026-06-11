# 📸 Fotobox – Raspberry Pi DSLR Smart Photo System

A modern, robust, and modular photo system based on a Raspberry Pi with DSLR camera control.

## Hardware Setup

| Component | Connection | Purpose |
|-----------|-----------|---------|
| Canon DSLR Camera | USB-C → Raspberry Pi | Photo capture via gphoto2 |
| HDMI Display | HDMI → Raspberry Pi | Web UI in kiosk mode |
| Trigger Button | Digital Pin → Arduino Nano | Physical shutter trigger |
| LED Ring (WS2812) | Digital Pin → Arduino Nano | Visual countdown |
| Arduino Nano | USB → Raspberry Pi | Serial communication bridge |

## System Flow

1. **Idle** – Display shows the Fotobox start screen; LED ring pulses gently.
2. **Button Press** – Arduino counts down via LED ring, the screen shows an animated countdown, then `countdown_complete` is sent over serial.
3. **Capture** – Raspberry Pi triggers the Canon camera via gphoto2, downloads and saves the photo.
4. **Review** – A downscaled preview is shown (full DSLR JPEGs are too heavy for the Pi 3 browser). Guests can take more photos or finish the session.
5. **Share** – Depending on `FOTOBOX_SHARE_MODE`:
   - `hotspot`: a WiFi access point is started; two QR codes (join WiFi → open gallery) let guests download their photos.
   - `nextcloud`: photos are uploaded in the background; a single QR code links to a public Nextcloud share.

## Project Structure

```
├── arduino/
│   └── fotobox_trigger/
│       └── fotobox_trigger.ino    # Arduino firmware (button + LED ring)
├── server/
│   ├── app.py                     # Flask web server + SSE + session handling
│   ├── camera.py                  # gphoto2 camera control module
│   ├── serial_reader.py           # Arduino serial communication module
│   ├── access_point.py            # nmcli hotspot management (profile reuse)
│   ├── nextcloud_client.py        # WebDAV upload + OCS share links
│   ├── previews.py                # Downscaled photo previews (Pi 3 friendly)
│   ├── config.py                  # Configuration (env vars / .env)
│   ├── static/                    # Frontend (style.css, app.js)
│   └── templates/                 # index.html (kiosk), download.html (guests)
├── tests/                         # pytest suite (all hardware mocked)
├── kiosk.sh                       # Chromium kiosk WITHOUT desktop environment
├── fotobox.service                # systemd unit: Flask server
├── fotobox-kiosk.service          # systemd unit: kiosk browser (xinit)
├── setup.sh                       # System setup script
└── .env.example                   # Configuration template
```

## Quick Start

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y gphoto2 libgphoto2-dev python3-pip python3-venv
```

### 2. Install Python Dependencies & Configure

```bash
cd ~/Fotobox
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # dann anpassen
```

### 3. Upload Arduino Firmware

Open `arduino/fotobox_trigger/fotobox_trigger.ino` in the Arduino IDE and upload to the Arduino Nano.

### 4. Run the Server

```bash
source venv/bin/activate
python -m server.app
```

The web UI will be available at `http://localhost:5000`.

### 5. Kiosk Mode ohne Desktop (empfohlen auf dem Pi 3)

Der Pi muss keine komplette Desktop-Umgebung laden – nur X-Server + Chromium.
Das spart ~150–250 MB RAM und mehrere Sekunden Bootzeit:

```bash
# 1. Boot auf Konsole stellen
sudo raspi-config   # System Options → Boot / Auto Login → Console Autologin

# 2. Minimales X + Chromium installieren (kein Desktop!)
sudo apt-get install -y xserver-xorg xinit chromium-browser

# 3. Kiosk-Service aktivieren
sudo cp fotobox-kiosk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fotobox-kiosk.service
```

## Configuration

Alle Einstellungen kommen aus Umgebungsvariablen bzw. der `.env`-Datei
(siehe [`.env.example`](.env.example)). Die wichtigsten:

| Variable | Default | Purpose |
|---|---|---|
| `FOTOBOX_SHARE_MODE` | `nextcloud` | `hotspot` oder `nextcloud` |
| `FOTOBOX_NC_URL` / `_USER` / `_PASS` | – | Nextcloud-Zugang (App-Passwort verwenden!) |
| `FOTOBOX_PHOTO_DIR` | `~/photos` | Lokaler Foto-Speicher |
| `FOTOBOX_SERIAL_PORT` | `/dev/ttyUSB0` | Arduino serial device |
| `FOTOBOX_ALLOW_REMOTE_CONTROL` | `0` | Kontroll-Endpoints nur von localhost (Security) |
| `FOTOBOX_REVIEW_SECONDS` | `30` | Auto-Reset des Review-Screens |
| `FOTOBOX_QR_TIMEOUT_SECONDS` | `120` | Auto-Reset des QR-Screens |
| `FOTOBOX_PREVIEW_MAX_SIZE` | `1280` | Max. Kantenlänge der Vorschaubilder |

## Security Notes

- Kontroll-Endpoints (Kiosk-UI, `/trigger`, `/session/*`, `/events`) sind nur von
  `localhost` erreichbar. Gäste im Hotspot sehen ausschließlich `/download` und `/photos/*`.
- Hotspot-Passwörter und Nextcloud-Session-IDs werden mit einem CSPRNG (`secrets`) erzeugt.
- Für Nextcloud unbedingt ein **App-Passwort** verwenden, kein Account-Passwort.
- Credentials gehören in die `.env` (ist via `.gitignore` vom Repo ausgeschlossen).

## Tests

```bash
source venv/bin/activate
pytest            # komplette Suite, keine Hardware nötig
```

## License

Apache 2.0 – see [LICENSE](LICENSE).
