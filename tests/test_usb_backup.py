"""Tests for the USB-Stick photo backup."""

import os
from unittest.mock import patch

from server.usb_backup import backup_photo, find_usb_mount


class TestFindUsbMount:
    def test_finds_two_level_mount(self, tmp_path):
        # /media/<user>/<label> – Label-Ordner ist der Mountpoint.
        root = tmp_path / "media"
        stick = root / "pi" / "USB"
        stick.mkdir(parents=True)
        with patch("server.usb_backup.os.path.ismount", lambda p: p == str(stick)):
            assert find_usb_mount(roots=(str(root),)) == str(stick)

    def test_finds_one_level_mount(self, tmp_path):
        root = tmp_path / "media"
        stick = root / "USB"
        stick.mkdir(parents=True)
        with patch("server.usb_backup.os.path.ismount", lambda p: p == str(stick)):
            assert find_usb_mount(roots=(str(root),)) == str(stick)

    def test_none_when_no_stick(self, tmp_path):
        root = tmp_path / "media"
        root.mkdir()
        with patch("server.usb_backup.os.path.ismount", lambda p: False):
            assert find_usb_mount(roots=(str(root),)) is None

    def test_skips_missing_root(self):
        assert find_usb_mount(roots=("/does/not/exist",)) is None


class TestBackupPhoto:
    def test_copies_into_subdir(self, tmp_path):
        photo = tmp_path / "foto_1.jpg"
        photo.write_bytes(b"\xff\xd8fake-jpeg")
        mount = tmp_path / "stick"
        mount.mkdir()

        dest = backup_photo(str(photo), mount=str(mount))

        assert dest is not None
        assert os.path.isfile(dest)
        assert dest.endswith(os.path.join("Fotobox", "foto_1.jpg"))
        assert open(dest, "rb").read() == b"\xff\xd8fake-jpeg"

    def test_returns_none_without_mount(self, tmp_path):
        photo = tmp_path / "foto_1.jpg"
        photo.write_bytes(b"x")
        with patch("server.usb_backup.find_usb_mount", return_value=None):
            assert backup_photo(str(photo)) is None

    def test_failure_is_non_fatal(self, tmp_path):
        photo = tmp_path / "missing.jpg"  # existiert nicht → copy schlägt fehl
        mount = tmp_path / "stick"
        mount.mkdir()
        assert backup_photo(str(photo), mount=str(mount)) is None
