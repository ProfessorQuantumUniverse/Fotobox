"""Tests for the manual update helper."""

from subprocess import CompletedProcess
from unittest.mock import mock_open, patch

import pytest

from server.updater import check_for_update, is_overlay_root, run_update_script


class TestIsOverlayRoot:
    def test_detects_overlay(self):
        mounts = "overlayroot / overlay rw,relatime 0 0\n"
        with patch("builtins.open", mock_open(read_data=mounts)):
            assert is_overlay_root() is True

    def test_normal_root(self):
        mounts = "/dev/mmcblk0p2 / ext4 rw,noatime 0 0\n"
        with patch("builtins.open", mock_open(read_data=mounts)):
            assert is_overlay_root() is False

    def test_missing_proc_is_not_overlay(self):
        with patch("builtins.open", side_effect=OSError):
            assert is_overlay_root() is False


class TestCheckForUpdate:
    def test_reports_behind_count(self):
        def fake_run(cmd, **kwargs):
            if cmd[1] == "fetch":
                return CompletedProcess(cmd, 0)
            return CompletedProcess(cmd, 0, stdout="3\n")

        with patch("server.updater.subprocess.run", side_effect=fake_run):
            assert check_for_update() == {"behind": 3}

    def test_up_to_date_returns_none(self):
        def fake_run(cmd, **kwargs):
            if cmd[1] == "fetch":
                return CompletedProcess(cmd, 0)
            return CompletedProcess(cmd, 0, stdout="0\n")

        with patch("server.updater.subprocess.run", side_effect=fake_run):
            assert check_for_update() is None

    def test_no_network_is_non_fatal(self):
        with patch("server.updater.subprocess.run", side_effect=OSError):
            assert check_for_update() is None


class TestRunUpdateScript:
    def test_failure_raises(self):
        failed = CompletedProcess(["bash"], 1, stdout="", stderr="merge conflict")
        with patch("server.updater.subprocess.run", return_value=failed):
            with pytest.raises(RuntimeError, match="merge conflict"):
                run_update_script()

    def test_success_passes(self):
        ok = CompletedProcess(["bash"], 0, stdout="done", stderr="")
        with patch("server.updater.subprocess.run", return_value=ok):
            run_update_script()  # darf nicht werfen
