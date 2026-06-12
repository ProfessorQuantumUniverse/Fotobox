"""Fotobox – Flask web application.

Serves the kiosk UI and bridges serial events from the Arduino
to the browser via Server-Sent Events (SSE).
"""

import base64
import hmac
import io
import json
import logging
import os
import queue
import subprocess
import time
from threading import Lock, Thread, Timer
from typing import Optional

import qrcode
from flask import Flask, Response, abort, jsonify, render_template, request, send_file, send_from_directory

from server.access_point import create_ap, generate_ap_credentials, stop_ap
from server.camera import capture_image, disable_display, read_ac_power
from server.config import (
    ALLOW_REMOTE_CONTROL,
    AP_IP,
    CAMERA_POWER_POLL,
    HOST,
    PHOTO_DIR,
    PORT,
    QR_TIMEOUT_SECONDS,
    REVIEW_SECONDS,
    UPDATE_CHECK_INTERVAL,
    UPDATE_PIN,
    USB_BACKUP,
    USB_POLL,
)
from server.previews import get_or_create_preview, warm_preview_async
from server.serial_reader import SerialReader
from server.updater import check_for_update, is_overlay_root, reboot, run_update_script
from server.usb_backup import backup_all_async, backup_photo_async, find_usb_mount

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Static assets ändern sich nur bei Deployments – aggressives Browser-Caching
# spart dem Pi 3 bei jedem Guest-Request Disk-I/O und CPU.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600

# Cache-Buster für app.js/style.css: ändert sich bei jedem Server-Start, damit
# der Kiosk-Browser nach einem Deployment nie mit veralteten Assets läuft.
STATIC_VERSION = int(time.time())

# Thread-safe queue for pushing events to SSE clients
event_queue: queue.Queue = queue.Queue()

# ── Security: control endpoints are localhost-only ───────────────────────
#
# Gäste, die mit dem Hotspot verbunden sind, dürfen nur die Download-Galerie
# und die Fotos sehen. Alles andere (Kiosk-UI, Trigger, Session-Verwaltung,
# SSE-Stream) ist dem lokalen Kiosk-Browser vorbehalten – sonst könnte jeder
# Gast Fotos auslösen, Sessions beenden oder den Hotspot abschalten.

PUBLIC_ENDPOINTS = {"download_gallery", "serve_photo", "serve_preview", "static", "status"}
_LOCAL_ADDRESSES = ("127.0.0.1", "::1", "::ffff:127.0.0.1")


@app.before_request
def _restrict_control_endpoints():
    if ALLOW_REMOTE_CONTROL:
        return None
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if request.remote_addr in _LOCAL_ADDRESSES:
        return None
    abort(403)


# ── Session tracking ──────────────────────────────────────────────────────

_session_lock = Lock()
_session_photos: list[str] = []  # filenames captured in the current session
_last_finished_session_photos: list[str] = []

# Debounce für den WebUI-Trigger: solange ein Countdown läuft, werden
# weitere Trigger ignoriert (verhindert doppelte Captures).
_trigger_lock = Lock()
_trigger_pending = False

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
            # Jedes Foto SOFORT auf einen evtl. gesteckten USB-Stick sichern –
            # auch wenn die Session später abgebrochen wird (alle Fotos zählen).
            if USB_BACKUP:
                backup_photo_async(filepath)
            # Preview im Hintergrund vorberechnen, damit der Review-Screen
            # sie sofort bekommt.
            warm_preview_async(filename)
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

# ── USB-Stick-Überwachung ────────────────────────────────────────────────

def _usb_storage_loop() -> None:
    """Poll for a mounted USB stick and toast on insert/removal.

    Beim Einstecken erscheint ein Toast und ALLE bereits aufgenommenen Fotos
    werden sofort gesichert; danach sichert jede neue Aufnahme zusätzlich auf
    den Stick (bis er wieder abgezogen wird). Das Abziehen meldet ebenfalls
    einen Toast.
    """
    present = find_usb_mount() is not None
    if present:
        # Stick steckte schon beim Start → vorhandene Fotos sichern (kein Toast).
        backup_all_async(PHOTO_DIR)
    while True:
        time.sleep(USB_POLL)
        now_present = find_usb_mount() is not None
        if now_present == present:
            continue
        present = now_present
        if present:
            logger.info("USB stick inserted – backing up all photos")
            backup_all_async(PHOTO_DIR)
            event_queue.put({"event": "usb_storage", "data": {"present": True}})
        else:
            logger.info("USB stick removed")
            event_queue.put({"event": "usb_storage", "data": {"present": False}})

# ── Update-Prüfung (manuell installiert, nur angeboten) ─────────────────

def _update_check_loop() -> None:
    """Poll the git remote and offer available updates to the kiosk UI.

    Es wird NICHTS automatisch installiert. Gibt es neue Commits, bekommt die
    UI ein ``update_available``-Event und zeigt eine antippbare Toast; die
    Installation startet erst nach PIN-Eingabe über POST /system/update.
    """
    while True:
        info = check_for_update()
        if info:
            event_queue.put({"event": "update_available", "data": info})
        time.sleep(UPDATE_CHECK_INTERVAL)


def _do_update() -> None:
    """Run update.sh, report progress to the UI, then reboot the Pi."""
    try:
        event_queue.put({"event": "update_progress",
                         "data": {"percent": 15, "message": "Neuer Code wird geladen"}})
        run_update_script()
        event_queue.put({"event": "update_progress",
                         "data": {"percent": 90, "message": "Neustart"}})
        reboot()
    except Exception as exc:
        logger.error("Update failed: %s", exc)
        event_queue.put({"event": "update_failed", "data": {"message": str(exc)}})


@app.route("/system/update", methods=["POST"])
def system_update():
    """Install an offered update (localhost-only, PIN-protected)."""
    data = request.get_json(silent=True) or {}
    pin = str(data.get("pin", ""))
    if not hmac.compare_digest(pin, UPDATE_PIN):
        return jsonify({"error": "PIN falsch"}), 403
    if is_overlay_root():
        return jsonify({
            "error": "Read-Only-System aktiv – Overlay zuerst deaktivieren "
                     "(sudo raspi-config nonint disable_overlayfs && sudo reboot)"
        }), 409
    logger.info("Update gestartet (PIN korrekt)")
    Thread(target=_do_update, daemon=True).start()
    return jsonify({"status": "updating"})


# ── Kamera-Stromüberwachung (USB-Laden) ──────────────────────────────────

def _camera_power_loop() -> None:
    """Poll the camera's AC/USB power state and toast on changes.

    Ein Toast erscheint nur beim Wechsel: Laden beginnt → "Kamera lädt",
    Laden endet → "Kamera am Akku". Die erste bekannte Messung legt nur den
    Ausgangszustand fest (kein Toast). Läuft eine Aufnahme, wird der Poll
    übersprungen (read_ac_power gibt dann None zurück).
    """
    last: Optional[bool] = None
    while True:
        time.sleep(CAMERA_POWER_POLL)
        state = read_ac_power()
        if state is None or state == last:
            continue
        if last is not None:  # nicht beim allerersten bekannten Wert toasten
            event_queue.put({"event": "camera_power", "data": {"charging": state}})
            logger.info("Camera power changed: charging=%s", state)
        last = state

# ── Routes ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main kiosk UI."""
    return render_template(
        "index.html",
        review_seconds=REVIEW_SECONDS,
        qr_timeout_seconds=QR_TIMEOUT_SECONDS,
        update_pin_length=len(UPDATE_PIN),
        static_v=STATIC_VERSION,
    )


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
    """Serve a captured photo (full resolution) as a forced download.

    ``as_attachment=True`` setzt ``Content-Disposition: attachment``, damit
    iOS Safari das Bild wirklich speichert (über das Teilen-/Download-Menü)
    statt es nur im Tab zu öffnen.
    """
    return send_from_directory(PHOTO_DIR, filename, as_attachment=True)


@app.route("/photos/preview/<filename>")
def serve_preview(filename):
    """Serve a downscaled, cached preview – much lighter for the Pi 3 browser."""
    path = get_or_create_preview(filename)
    if path is None:
        abort(404)
    return send_file(path, mimetype="image/jpeg")


@app.route("/status")
def status():
    """Health-check endpoint."""
    return jsonify({"status": "ok"})


def _make_qr_data_uri(payload: str) -> str:
    """Generate a QR code and return it as a base64 PNG data URI."""
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _make_wifi_qr(ssid: str, password: str) -> str:
    """Generate a WiFi QR code and return it as a base64 PNG data URI."""
    # Sonderzeichen in SSID/Passwort müssen laut WiFi-QR-Spec escaped werden.
    def esc(value: str) -> str:
        for ch in ("\\", ";", ",", ":", '"'):
            value = value.replace(ch, "\\" + ch)
        return value

    return _make_qr_data_uri(f"WIFI:T:WPA;S:{esc(ssid)};P:{esc(password)};;")


@app.route("/session/finish", methods=["POST"])
def session_finish():
    """Finalise the current session, start an AP/Nextcloud upload, and return QR code data."""
    with _session_lock:
        photos = list(_session_photos)
        _session_photos.clear()
        _last_finished_session_photos.clear()
        _last_finished_session_photos.extend(photos)

    if not photos:
        return jsonify({"error": "Keine Fotos in dieser Session"}), 400

    ssid, password = generate_ap_credentials()
    download_url = f"http://{AP_IP}:{PORT}/download"

    # AP synchron im Request starten wäre zu langsam – Hintergrund reicht,
    # die Gäste brauchen ein paar Sekunden zum Scannen.
    Thread(target=create_ap, args=(ssid, password), daemon=True).start()

    logger.info("Session finished: %d photo(s), AP SSID=%s", len(photos), ssid)
    return jsonify({
        "share_mode": "hotspot",
        "photos": photos,
        "ssid": ssid,
        "password": password,
        "download_url": download_url,
        "wifi_qr": _make_wifi_qr(ssid, password),
        "download_qr": _make_qr_data_uri(download_url),
    })


@app.route("/session/stop-ap", methods=["POST"])
def session_stop_ap():
    """Tear down the temporary Access Point (profile is kept for reuse)."""
    Thread(target=stop_ap, daemon=True).start()
    return jsonify({"status": "stopping"})


def _do_shutdown() -> None:
    """Bring everything down cleanly, then power off the Pi.

    Erst den Hotspot abbauen und Puffer auf die SD-Karte schreiben (``sync``),
    damit das nächste Booten sauber bleibt – dann ``sudo shutdown``.
    """
    try:
        stop_ap()
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("stop_ap during shutdown failed: %s", exc)
    try:
        subprocess.run(["sync"], timeout=10)
    except Exception:  # pragma: no cover - best effort
        pass
    try:
        subprocess.run(["sudo", "shutdown", "-h", "now"], timeout=10)
    except Exception as exc:  # pragma: no cover - best effort
        logger.error("shutdown command failed: %s", exc)


@app.route("/system/shutdown", methods=["POST"])
def system_shutdown():
    """Gracefully power the Pi off (localhost-only, kiosk shutdown menu)."""
    logger.info("Shutdown requested via kiosk menu")
    Thread(target=_do_shutdown, daemon=True).start()
    return jsonify({"status": "shutting_down"})


def _do_reboot() -> None:
    """Bring everything down cleanly, then reboot the Pi.

    Wie ``_do_shutdown``, nur ``shutdown -r`` statt ``-h`` – dieselbe sudoers-
    Regel deckt beides ab.
    """
    try:
        stop_ap()
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("stop_ap during reboot failed: %s", exc)
    try:
        subprocess.run(["sync"], timeout=10)
    except Exception:  # pragma: no cover - best effort
        pass
    try:
        subprocess.run(["sudo", "shutdown", "-r", "now"], timeout=10)
    except Exception as exc:  # pragma: no cover - best effort
        logger.error("reboot command failed: %s", exc)


@app.route("/system/reboot", methods=["POST"])
def system_reboot():
    """Gracefully reboot the Pi (localhost-only, kiosk shutdown menu)."""
    logger.info("Reboot requested via kiosk menu")
    Thread(target=_do_reboot, daemon=True).start()
    return jsonify({"status": "rebooting"})


@app.route("/trigger", methods=["POST"])
def trigger():
    """Simuliert den physischen Button aus der WebUI heraus."""
    global _trigger_pending
    with _trigger_lock:
        if _trigger_pending:
            return jsonify({"status": "already_running"}), 409
        _trigger_pending = True

    event_queue.put({"event": "button_pressed"})

    # Warte 8 Sekunden (wie der Arduino es tun würde) und feuere dann das Foto
    def trigger_photo():
        global _trigger_pending
        try:
            _on_serial_message("countdown_complete")
        finally:
            with _trigger_lock:
                _trigger_pending = False

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


# ── Startup ─────────────────────────────────────────────────────────────

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
    Thread(target=disable_display, daemon=True).start()
    if CAMERA_POWER_POLL > 0:
        Thread(target=_camera_power_loop, daemon=True).start()
    if USB_BACKUP and USB_POLL > 0:
        Thread(target=_usb_storage_loop, daemon=True).start()
    if UPDATE_CHECK_INTERVAL > 0:
        Thread(target=_update_check_loop, daemon=True).start()
    logger.info("Fotobox running")
    try:
        app.run(host=HOST, port=PORT, debug=False, threaded=True)
    finally:
        if serial_reader is not None:
            serial_reader.stop()
