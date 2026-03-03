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
