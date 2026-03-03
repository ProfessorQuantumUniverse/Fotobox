"""Tests for the camera module."""

import os
from unittest.mock import MagicMock, patch

import pytest

from server.camera import capture_image, ensure_photo_dir


class TestEnsurePhotoDir:
    """Tests for ensure_photo_dir."""

    def test_creates_directory(self, tmp_path):
        photo_dir = str(tmp_path / "photos")
        with patch("server.camera.PHOTO_DIR", photo_dir):
            result = ensure_photo_dir()
        assert result == photo_dir
        assert os.path.isdir(photo_dir)

    def test_existing_directory(self, tmp_path):
        photo_dir = str(tmp_path / "photos")
        os.makedirs(photo_dir)
        with patch("server.camera.PHOTO_DIR", photo_dir):
            result = ensure_photo_dir()
        assert result == photo_dir


class TestCaptureImage:
    """Tests for capture_image."""

    def test_successful_capture(self, tmp_path):
        photo_dir = str(tmp_path / "photos")
        os.makedirs(photo_dir, exist_ok=True)

        def fake_run(cmd, **kwargs):
            # Simulate gphoto2 creating a file
            filepath = cmd[cmd.index("--filename") + 1]
            with open(filepath, "wb") as f:
                f.write(b"\xff\xd8fake-jpeg")
            return MagicMock(stdout="New file downloaded", returncode=0)

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("subprocess.run", side_effect=fake_run):
            result = capture_image()

        assert result.startswith(photo_dir)
        assert result.endswith(".jpg")
        assert os.path.isfile(result)

    def test_gphoto2_not_installed(self, tmp_path):
        photo_dir = str(tmp_path / "photos")

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="gphoto2 is not installed"):
                capture_image()

    def test_gphoto2_failure(self, tmp_path):
        import subprocess
        photo_dir = str(tmp_path / "photos")

        exc = subprocess.CalledProcessError(1, "gphoto2", stderr="No camera found")
        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("subprocess.run", side_effect=exc):
            with pytest.raises(RuntimeError, match="Camera capture failed"):
                capture_image()
