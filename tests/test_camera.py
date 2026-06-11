"""Tests for the camera module."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from server.camera import capture_image, ensure_photo_dir


def _gphoto_router(gphoto_behaviour):
    """Build a subprocess.run side effect that ignores the pkill pre-step.

    ``capture_image`` first runs ``pkill -f gphoto2`` and then the actual
    gphoto2 command – the mock must only apply the behaviour to the latter.
    """

    def side_effect(cmd, **kwargs):
        if cmd[0] == "pkill":
            return MagicMock(returncode=1)
        return gphoto_behaviour(cmd, **kwargs)

    return side_effect


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

        def fake_gphoto(cmd, **kwargs):
            # Simulate gphoto2 creating a file
            filepath = cmd[cmd.index("--filename") + 1]
            with open(filepath, "wb") as f:
                f.write(b"\xff\xd8fake-jpeg")
            return MagicMock(stdout="New file downloaded", returncode=0)

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("server.camera.subprocess.run", side_effect=_gphoto_router(fake_gphoto)):
            result = capture_image()

        assert result.startswith(photo_dir)
        assert result.endswith(".jpg")
        assert os.path.isfile(result)

    def test_gphoto2_not_installed(self, tmp_path):
        photo_dir = str(tmp_path / "photos")

        def fake_gphoto(cmd, **kwargs):
            raise FileNotFoundError

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("server.camera.subprocess.run", side_effect=_gphoto_router(fake_gphoto)):
            with pytest.raises(RuntimeError, match="gphoto2 is not installed"):
                capture_image()

    def test_gphoto2_failure(self, tmp_path):
        photo_dir = str(tmp_path / "photos")

        def fake_gphoto(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, "gphoto2", stderr="No camera found")

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("server.camera.subprocess.run", side_effect=_gphoto_router(fake_gphoto)):
            with pytest.raises(RuntimeError, match="Camera capture failed"):
                capture_image()

    def test_gphoto2_timeout(self, tmp_path):
        photo_dir = str(tmp_path / "photos")

        def fake_gphoto(cmd, **kwargs):
            raise subprocess.TimeoutExpired("gphoto2", 30)

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("server.camera.subprocess.run", side_effect=_gphoto_router(fake_gphoto)):
            with pytest.raises(RuntimeError, match="timed out"):
                capture_image()

    def test_missing_pkill_is_not_fatal(self, tmp_path):
        """pkill fehlt auf Dev-Rechnern – Capture muss trotzdem funktionieren."""
        photo_dir = str(tmp_path / "photos")
        os.makedirs(photo_dir, exist_ok=True)

        def side_effect(cmd, **kwargs):
            if cmd[0] == "pkill":
                raise FileNotFoundError
            filepath = cmd[cmd.index("--filename") + 1]
            with open(filepath, "wb") as f:
                f.write(b"\xff\xd8fake-jpeg")
            return MagicMock(stdout="ok", returncode=0)

        with patch("server.camera.PHOTO_DIR", photo_dir), \
             patch("server.camera.subprocess.run", side_effect=side_effect):
            result = capture_image()

        assert os.path.isfile(result)
