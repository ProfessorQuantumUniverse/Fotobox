"""Fotobox – Flask web application.

Serves the kiosk UI and bridges serial events from the Arduino
to the browser via Server-Sent Events (SSE).
"""

import json
import logging
import os
import queue
from typing import Optional

from flask import Flask, Response, jsonify, render_template, send_from_directory

from server.camera import capture_image
from server.config import HOST, PHOTO_DIR, PORT, REVIEW_SECONDS
from server.serial_reader import SerialReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Thread-safe queue for pushing events to SSE clients
event_queue: queue.Queue = queue.Queue()

# ── Serial event handler ─────────────────────────────────────────────────

def _on_serial_message(message: str) -> None:
    """Handle a message received from the Arduino."""
    logger.info("Arduino event: %s", message)

    if message == "countdown_complete":
        event_queue.put({"event": "countdown_complete"})
        try:
            filepath = capture_image()
            filename = os.path.basename(filepath)
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
    os.makedirs(PHOTO_DIR, exist_ok=True)
    return app


if __name__ == "__main__":
    create_app()
    start_serial()
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    finally:
        if serial_reader is not None:
            serial_reader.stop()
