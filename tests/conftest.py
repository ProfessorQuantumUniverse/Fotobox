"""Shared pytest fixtures for the Fotobox test suite."""

import os
from unittest.mock import patch

import pytest
from PIL import Image

import server.app as app_module
from server.app import create_app


@pytest.fixture
def photo_dir(tmp_path):
    """A temporary photo directory, patched into all modules that use it."""
    d = str(tmp_path / "photos")
    os.makedirs(d, exist_ok=True)
    with patch("server.app.PHOTO_DIR", d), \
         patch("server.camera.PHOTO_DIR", d), \
         patch("server.previews.PHOTO_DIR", d):
        yield d


@pytest.fixture
def client(photo_dir):
    """Flask test client with a clean session and temporary photo directory."""
    app = create_app()
    app.config["TESTING"] = True

    # Saubere Session pro Test
    with app_module._session_lock:
        app_module._session_photos.clear()
        app_module._last_finished_session_photos.clear()

    with app.test_client() as client:
        yield client


def make_test_jpeg(path: str, size: tuple[int, int] = (1600, 1200)) -> None:
    """Write a real JPEG file (needed for the preview pipeline)."""
    img = Image.new("RGB", size, color=(120, 120, 120))
    img.save(path, format="JPEG")
