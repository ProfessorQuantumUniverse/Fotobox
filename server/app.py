"""Fotobox – Flask web application.

Serves the kiosk UI and bridges serial events from the Arduino
to the browser via Server-Sent Events (SSE).
"""

import base64
import io
import json
import logging
import os
import queue
from threading import Lock, Thread, Timer
from typing import Optional

import qrcode
from flask import Flask, Response, jsonify, render_template, send_from_directory

from server.access_point import create_ap, generate_ap_credentials, stop_ap
from server.camera import capture_image
from server.config import AP_IP, HOST, PHOTO_DIR, PORT, REVIEW_SECONDS
from server.serial_reader import SerialReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Thread-safe queue for pushing events to SSE clients
event_queue: queue.Queue = queue.Queue()

# ── Session tracking ──────────────────────────────────────────────────────

_session_lock = Lock()
_session_photos: list[str] = []  # filenames captured in the current session
_last_finished_session_photos: list[str] = []

# ── Serial event handler ─────────────────────────────────────────────────

def _on_serial_message(message: str) -> None:
    """Handle a message received from the Arduino."""
    logger.info("Arduino event: %s", message)

    if message == "countdown_complete":
        event_queue.put({"event": "countdown_complete"})
        try:
            filepath = capture_image()
            filename = os.path.basename(filepath)
            with _session_lock:
                _session_photos.append(filename)
            event_queue.put({
                "event": "photo_taken",
                "data": {"filename": filename},
            })
        except RuntimeError as exc:
            logger.error("Capture failed: %s", exc)
            event_queue.put({
                "event": "error",
                "data": {"message": str(exc)},
            })

    elif message == "button_pressed":
        event_queue.put({"event": "button_pressed"})

# ── Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main kiosk UI."""
    return render_template("index.html", review_seconds=REVIEW_SECONDS)


@app.route("/events")
def events():
    """SSE endpoint – streams events to the browser."""

    def stream():
        while True:
            try:
                msg = event_queue.get(timeout=30)
                data = json.dumps(msg)
                yield f"data: {data}\n\n"
            except queue.Empty:
                # keep-alive comment
                yield ": heartbeat\n\n"

    return Response(stream(), mimetype="text/event-stream")


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    """Serve a captured photo from the photo directory."""
    return send_from_directory(PHOTO_DIR, filename)


@app.route("/status")
def status():
    """Health-check endpoint."""
    return jsonify({"status": "ok"})


def _make_wifi_qr(ssid: str, password: str) -> str:
    """Generate a WiFi QR code and return it as a base64 PNG data URI."""
    wifi_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"
    img = qrcode.make(wifi_string)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _make_text_qr(text: str) -> str:
    """Generate a text QR code and return it as a base64 PNG data URI."""
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@app.route("/session/finish", methods=["POST"])
def session_finish():
    """Finalise the current session, start an AP, and return QR code data."""
    with _session_lock:
        photos = list(_session_photos)
        _session_photos.clear()
        _last_finished_session_photos.clear()
        _last_finished_session_photos.extend(photos)

    ssid, password = generate_ap_credentials()
    wifi_qr_data_uri = _make_wifi_qr(ssid, password)
    download_url = f"http://{AP_IP}:{PORT}/download"
    download_qr_data_uri = _make_text_qr(download_url)

    # Start the AP in a background thread; non-daemon so shutdown waits for it.
    Thread(target=create_ap, args=(ssid, password)).start()

    logger.info("Session finished: %d photo(s), AP SSID=%s", len(photos), ssid)
    return jsonify({
        "photos": photos,
        "ssid": ssid,
        "password": password,
        # Backward-compatible aliases:
        "url": download_url,
        "qr": wifi_qr_data_uri,
        # Explicit values for UI:
        "download_url": download_url,
        "wifi_qr": wifi_qr_data_uri,
        "download_qr": download_qr_data_uri,
    })


@app.route("/session/stop-ap", methods=["POST"])
def session_stop_ap():
    """Tear down the temporary Access Point."""
    Thread(target=stop_ap).start()
    return jsonify({"status": "stopping"})

@app.route("/trigger", methods=["POST"])
def trigger():
    """Simuliert den physischen Button aus der WebUI heraus."""
    # Sende das Button-Pressed Event (Startet den Countdown im Browser)
    event_queue.put({"event": "button_pressed"})
    
    # Warte 8 Sekunden (wie der Arduino es tun würde) und feuere dann das Foto
    def trigger_photo():
        _on_serial_message("countdown_complete")

    Timer(8.0, trigger_photo).start()
    
    return jsonify({"status": "triggered"})

@app.route("/download")
def download_gallery():
    """Show a mobile-friendly gallery of the most recent session photos."""
    files: list[str] = []
    with _session_lock:
        if _last_finished_session_photos:
            files = list(_last_finished_session_photos)

    if not files and os.path.exists(PHOTO_DIR):
        all_entries = sorted(os.listdir(PHOTO_DIR), reverse=True)
        files = [f for f in all_entries if f.lower().endswith(".jpg")][:10]

    return render_template("download.html", photos=files)


# ── Startup ───────────────────────────────────────────────────────────────

serial_reader: Optional[SerialReader] = None


def start_serial() -> None:
    """Attempt to start the serial reader (non-fatal on failure)."""
    global serial_reader
    try:
        serial_reader = SerialReader(on_message=_on_serial_message)
        serial_reader.start()
    except Exception as exc:
        logger.warning("Serial reader not available: %s (running without Arduino)", exc)
        serial_reader = None


def create_app():
    """Application factory used by tests and production."""
    try:
        os.makedirs(PHOTO_DIR, exist_ok=True)
    except PermissionError as exc:
        logger.error(
            "Cannot create photo directory '%s': %s. "
            "Set FOTOBOX_PHOTO_DIR to a writable path.",
            PHOTO_DIR,
            exc,
        )
        raise
    return app


if __name__ == "__main__":
    create_app()
    start_serial()
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    finally:
        if serial_reader is not None:
            serial_reader.stop()
