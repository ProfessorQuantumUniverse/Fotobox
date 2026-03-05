"""Tests for the access_point module."""

import subprocess
from unittest.mock import call, patch

import pytest

from server.access_point import create_ap, generate_ap_credentials, stop_ap


class TestGenerateApCredentials:
    """Tests for generate_ap_credentials."""

    def test_returns_tuple(self):
        ssid, password = generate_ap_credentials()
        assert isinstance(ssid, str)
        assert isinstance(password, str)

    def test_ssid_format(self):
        ssid, _ = generate_ap_credentials()
        assert ssid.startswith("Fotobox-")
        suffix = ssid[len("Fotobox-"):]
        assert len(suffix) == 4
        assert suffix.isdigit()

    def test_password_length(self):
        _, password = generate_ap_credentials()
        assert len(password) == 12

    def test_credentials_are_random(self):
        results = {generate_ap_credentials() for _ in range(10)}
        # With 10^4 possible SSIDs there is a ~99.9 % chance of at least 2 different ones.
        assert len(results) > 1


class TestCreateAp:
    """Tests for create_ap."""

    def test_success(self):
        with patch("server.access_point._run") as mock_run:
            result = create_ap("Fotobox-1234", "MyPass01")
        assert result is True
        # delete, add, up
        assert mock_run.call_count == 3

    def test_nmcli_not_found(self):
        with patch("server.access_point._run", side_effect=FileNotFoundError):
            result = create_ap("Fotobox-1234", "MyPass01")
        assert result is False

    def test_nmcli_error(self):
        exc = subprocess.CalledProcessError(1, "nmcli", stderr="error")

        def side_effect(cmd, **kwargs):
            # Allow the delete call (check=False), fail on add
            if "add" in cmd:
                raise exc
            from unittest.mock import MagicMock
            return MagicMock()

        with patch("server.access_point._run", side_effect=side_effect):
            result = create_ap("Fotobox-1234", "MyPass01")
        assert result is False


class TestStopAp:
    """Tests for stop_ap."""

    def test_stop_runs_nmcli(self):
        with patch("server.access_point._run") as mock_run:
            stop_ap()
        assert mock_run.call_count == 2

    def test_stop_handles_missing_nmcli(self):
        with patch("server.access_point._run", side_effect=FileNotFoundError):
            stop_ap()  # must not raise
