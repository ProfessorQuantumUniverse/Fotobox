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

1. **Idle** – Display shows live preview with "Press the button" prompt; LED ring pulses gently.
2. **Button Press** – Arduino counts down via LED ring (blue → orange → red), then sends `countdown_complete` over serial.
3. **Capture** – Raspberry Pi triggers the Canon camera via gphoto2, downloads and saves the photo.
4. **Review** – Captured photo is displayed on screen for a few seconds before returning to idle.

## Project Structure

```
├── arduino/
│   └── fotobox_trigger/
│       └── fotobox_trigger.ino    # Arduino firmware (button + LED ring)
├── server/
│   ├── app.py                     # Flask web server + camera + serial
│   ├── camera.py                  # gphoto2 camera control module
│   ├── serial_reader.py           # Arduino serial communication module
│   ├── config.py                  # Configuration constants
│   ├── static/
│   │   ├── style.css              # Frontend styles
│   │   └── app.js                 # Frontend logic
│   └── templates/
│       └── index.html             # Main UI template
├── tests/
│   ├── test_camera.py             # Camera module tests
│   ├── test_serial_reader.py      # Serial reader tests
│   └── test_app.py                # Flask app tests
├── requirements.txt               # Python dependencies
├── setup.sh                       # System setup script
└── fotobox.service                # systemd service file
```

## Quick Start

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y gphoto2 libgphoto2-dev python3-pip python3-venv
```

### 2. Install Python Dependencies

```bash
cd /home/pi/Fotobox
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Upload Arduino Firmware

Open `arduino/fotobox_trigger/fotobox_trigger.ino` in the Arduino IDE and upload to the Arduino Nano.

### 4. Run the Server

```bash
source venv/bin/activate
python server/app.py
```

The web UI will be available at `http://localhost:5000`.

### 5. Kiosk Mode (Optional)

To launch the browser in kiosk mode on the Raspberry Pi:

```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:5000
```

## Configuration

Edit `server/config.py` to adjust:

- Serial port and baud rate
- Photo storage directory
- Countdown duration
- Camera capture settings

## License

Apache 2.0 – see [LICENSE](LICENSE).
