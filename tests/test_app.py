"""Tests for the Flask application."""

import json
import os
from unittest.mock import patch

import server.app as app_module

from tests.conftest import make_test_jpeg


class TestRoutes:
    """Test HTTP routes."""

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"FOTOBOX" in resp.data

    def test_status(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_serve_photo(self, client, photo_dir):
        test_photo = os.path.join(photo_dir, "test.jpg")
        with open(test_photo, "wb") as f:
            f.write(b"\xff\xd8fake-jpeg")

        resp = client.get("/photos/test.jpg")
        assert resp.status_code == 200
        # iOS lädt nur herunter, wenn Content-Disposition: attachment gesetzt ist.
        assert "attachment" in resp.headers.get("Content-Disposition", "")

    def test_serve_photo_not_found(self, client):
        resp = client.get("/photos/nonexistent.jpg")
        assert resp.status_code == 404

    def test_serve_photo_traversal_blocked(self, client):
        resp = client.get("/photos/../config.py")
        assert resp.status_code in (302, 404)

    def test_events_endpoint_content_type(self, client):
        """Verify the SSE endpoint returns the correct content type."""
        # Push a test event so the stream yields data and we can read the response
        app_module.event_queue.put({"event": "test"})
        resp = client.get("/events")
        assert "text/event-stream" in resp.content_type


class TestPreviews:
    """Tests for the downscaled preview endpoint."""

    def test_preview_is_generated_and_smaller(self, client, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "foto_1.jpg"), size=(3200, 2400))

        resp = client.get("/photos/preview/foto_1.jpg")
        assert resp.status_code == 200
        assert resp.mimetype == "image/jpeg"

        original_size = os.path.getsize(os.path.join(photo_dir, "foto_1.jpg"))
        assert len(resp.data) < original_size

    def test_preview_is_cached(self, client, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "foto_2.jpg"))

        client.get("/photos/preview/foto_2.jpg")
        cache_file = os.path.join(photo_dir, ".previews", "foto_2.jpg")
        assert os.path.isfile(cache_file)
        first_mtime = os.path.getmtime(cache_file)

        client.get("/photos/preview/foto_2.jpg")
        assert os.path.getmtime(cache_file) == first_mtime

    def test_preview_missing_photo_404(self, client):
        resp = client.get("/photos/preview/does-not-exist.jpg")
        assert resp.status_code == 404


class TestAccessRestriction:
    """Control endpoints must only be reachable from localhost."""

    CONTROL_PATHS = [
        ("get", "/"),
        ("get", "/events"),
        ("post", "/trigger"),
        ("post", "/session/finish"),
        ("post", "/session/stop-ap"),
    ]

    def test_remote_client_blocked_from_control_endpoints(self, client):
        for method, path in self.CONTROL_PATHS:
            resp = getattr(client, method)(path, environ_base={"REMOTE_ADDR": "10.42.0.55"})
            assert resp.status_code == 403, f"{path} must be localhost-only"

    def test_remote_client_can_use_gallery(self, client, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "foto_g.jpg"))
        guest = {"REMOTE_ADDR": "10.42.0.55"}

        assert client.get("/download", environ_base=guest).status_code == 200
        assert client.get("/photos/foto_g.jpg", environ_base=guest).status_code == 200
        assert client.get("/photos/preview/foto_g.jpg", environ_base=guest).status_code == 200

    def test_localhost_allowed(self, client):
        assert client.get("/").status_code == 200

    def test_remote_control_can_be_enabled(self, client):
        with patch("server.app.ALLOW_REMOTE_CONTROL", True):
            resp = client.get("/", environ_base={"REMOTE_ADDR": "10.42.0.55"})
        assert resp.status_code == 200


class TestSessionFinishHotspot:
    """Tests for /session/finish in hotspot mode."""

    def _finish(self, client):
        with patch("server.app.create_ap", return_value=True) as mock_create:
            resp = client.post("/session/finish")
        return resp, mock_create

    def test_returns_qr_and_credentials(self, client):
        with app_module._session_lock:
            app_module._session_photos.extend(["foto_1.jpg", "foto_2.jpg"])

        resp, _ = self._finish(client)

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["share_mode"] == "hotspot"
        assert data["ssid"].startswith("Fotobox-")
        assert len(data["password"]) >= 8
        assert data["wifi_qr"].startswith("data:image/png;base64,")
        assert data["download_qr"].startswith("data:image/png;base64,")
        assert "/download" in data["download_url"]
        assert data["photos"] == ["foto_1.jpg", "foto_2.jpg"]

    def test_clears_session(self, client):
        with app_module._session_lock:
            app_module._session_photos.append("foto_test.jpg")

        resp, _ = self._finish(client)

        assert resp.status_code == 200
        assert "foto_test.jpg" in json.loads(resp.data)["photos"]
        with app_module._session_lock:
            assert app_module._session_photos == []

    def test_empty_session_rejected(self, client):
        resp, _ = self._finish(client)
        assert resp.status_code == 400

    def test_session_stop_ap(self, client):
        with patch("server.app.stop_ap"):
            resp = client.post("/session/stop-ap")
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "stopping"


class TestSystemShutdown:
    """The kiosk shutdown menu powers the Pi off cleanly."""

    def test_shutdown_triggers_command(self, client):
        # Den eigentlichen Shutdown-Thread synchron ausführen und stop_ap +
        # shutdown-Aufruf prüfen – ohne den Rechner wirklich auszuschalten.
        def run_inline(target, daemon=False):
            class _T:
                def start(self_inner):
                    target()
            return _T()

        with patch("server.app.Thread", side_effect=run_inline), \
             patch("server.app.stop_ap") as mock_stop, \
             patch("server.app.subprocess.run") as mock_run:
            resp = client.post("/system/shutdown")

        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "shutting_down"
        mock_stop.assert_called_once()
        # Letzter Aufruf muss der shutdown-Befehl sein.
        assert mock_run.call_args_list[-1].args[0][:2] == ["sudo", "shutdown"]

    def test_shutdown_is_localhost_only(self, client):
        resp = client.post("/system/shutdown", environ_base={"REMOTE_ADDR": "10.42.0.55"})
        assert resp.status_code == 403



class TestSystemUpdate:
    """Updates werden nur angeboten – installiert wird erst nach PIN-Eingabe."""

    def test_wrong_pin_rejected(self, client):
        resp = client.post("/system/update", json={"pin": "0000"})
        assert resp.status_code == 403

    def test_missing_pin_rejected(self, client):
        resp = client.post("/system/update", json={})
        assert resp.status_code == 403

    def test_overlay_blocks_update(self, client):
        with patch("server.app.is_overlay_root", return_value=True):
            resp = client.post("/system/update", json={"pin": "5050"})
        assert resp.status_code == 409
        assert "Read-Only" in json.loads(resp.data)["error"]

    def test_correct_pin_starts_update(self, client):
        with patch("server.app.is_overlay_root", return_value=False), \
             patch("server.app.Thread") as mock_thread:
            resp = client.post("/system/update", json={"pin": "5050"})
        assert resp.status_code == 200
        assert json.loads(resp.data)["status"] == "updating"
        mock_thread.assert_called_once()

    def test_update_is_localhost_only(self, client):
        resp = client.post(
            "/system/update",
            json={"pin": "5050"},
            environ_base={"REMOTE_ADDR": "10.42.0.55"},
        )
        assert resp.status_code == 403


class TestTrigger:
    """Tests for the WebUI trigger endpoint."""

    def test_trigger_emits_button_pressed(self, client):
        # Leere Queue
        while not app_module.event_queue.empty():
            app_module.event_queue.get_nowait()

        with patch("server.app.Timer") as mock_timer:
            resp = client.post("/trigger")
            assert resp.status_code == 200
            mock_timer.assert_called_once()

        event = app_module.event_queue.get_nowait()
        assert event["event"] == "button_pressed"

        # Debounce zurücksetzen für andere Tests
        with app_module._trigger_lock:
            app_module._trigger_pending = False

    def test_trigger_debounce(self, client):
        with patch("server.app.Timer"):
            assert client.post("/trigger").status_code == 200
            assert client.post("/trigger").status_code == 409

        with app_module._trigger_lock:
            app_module._trigger_pending = False


class TestDownloadGallery:
    """Tests for the guest download page."""

    def test_shows_last_session_photos(self, client):
        with app_module._session_lock:
            app_module._last_finished_session_photos.extend(["foto_a.jpg", "foto_b.jpg"])

        resp = client.get("/download")
        assert resp.status_code == 200
        assert b"foto_a.jpg" in resp.data
        assert b"foto_b.jpg" in resp.data

    def test_falls_back_to_recent_photos(self, client, photo_dir):
        make_test_jpeg(os.path.join(photo_dir, "foto_old.jpg"))

        resp = client.get("/download")
        assert resp.status_code == 200
        assert b"foto_old.jpg" in resp.data

    def test_empty_gallery(self, client):
        resp = client.get("/download")
        assert resp.status_code == 200
        assert "Keine Fotos".encode() in resp.data
