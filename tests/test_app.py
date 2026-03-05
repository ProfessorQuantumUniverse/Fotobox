"""Tests for the Flask application."""

import json
import os
from unittest.mock import patch

import pytest

from server.app import create_app


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temporary photo directory."""
    photo_dir = str(tmp_path / "photos")
    os.makedirs(photo_dir, exist_ok=True)

    with patch("server.app.PHOTO_DIR", photo_dir), \
         patch("server.camera.PHOTO_DIR", photo_dir):
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client


class TestRoutes:
    """Test HTTP routes."""

    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Fotobox" in resp.data

    def test_status(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "ok"

    def test_serve_photo(self, client, tmp_path):
        photo_dir = str(tmp_path / "photos")
        os.makedirs(photo_dir, exist_ok=True)
        test_photo = os.path.join(photo_dir, "test.jpg")
        with open(test_photo, "wb") as f:
            f.write(b"\xff\xd8fake-jpeg")

        with patch("server.app.PHOTO_DIR", photo_dir):
            resp = client.get("/photos/test.jpg")
            assert resp.status_code == 200

    def test_serve_photo_not_found(self, client):
        resp = client.get("/photos/nonexistent.jpg")
        assert resp.status_code == 404

    def test_events_endpoint_content_type(self, client):
        """Verify the SSE endpoint returns the correct content type."""
        from server.app import event_queue
        # Push a test event so the stream yields data and we can read the response
        event_queue.put({"event": "test"})
        resp = client.get("/events")
        assert "text/event-stream" in resp.content_type


class TestSessionFinish:
    """Tests for the /session/finish endpoint."""

    def test_session_finish_returns_qr_and_credentials(self, client):
        """session/finish should return ssid, password, url, qr and photos."""
        with patch("server.app.create_ap", return_value=True), \
             patch("server.app._session_photos", ["foto_1.jpg", "foto_2.jpg"]):
            resp = client.post("/session/finish")

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "ssid" in data
        assert data["ssid"].startswith("Fotobox-")
        assert "password" in data
        assert "url" in data
        assert "qr" in data
        assert data["qr"].startswith("data:image/png;base64,")
        assert "photos" in data

    def test_session_finish_clears_session(self, client):
        """session/finish should clear the in-memory session photo list."""
        from server.app import _session_photos, _session_lock
        with _session_lock:
            _session_photos.clear()
            _session_photos.append("foto_test.jpg")

        with patch("server.app.create_ap", return_value=True):
            resp = client.post("/session/finish")

        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "foto_test.jpg" in data["photos"]

        with _session_lock:
            assert _session_photos == []

    def test_session_stop_ap(self, client):
        """session/stop-ap should return status stopping."""
        with patch("server.app.stop_ap"):
            resp = client.post("/session/stop-ap")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["status"] == "stopping"
