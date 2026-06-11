"""Tests for the access_point module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

import server.access_point as ap
from server.access_point import (
    create_ap,
    generate_ap_credentials,
    remove_ap_profile,
    reset_ap_credentials,
    stop_ap,
)


@pytest.fixture(autouse=True)
def reset_module_state():
    """Each test starts with no cached credentials and no known profile."""
    reset_ap_credentials()
    ap._profile_credentials = None
    ap._ap_active = False
    yield
    reset_ap_credentials()
    ap._profile_credentials = None
    ap._ap_active = False


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

    def test_credentials_cached_per_process(self):
        """Wiederholte Sessions verwenden dieselben Zugangsdaten –
        Gäste bleiben verbunden, nmcli muss das Profil nicht neu schreiben."""
        first = generate_ap_credentials()
        second = generate_ap_credentials()
        assert first == second

    def test_reset_generates_new_credentials(self):
        first = generate_ap_credentials()
        reset_ap_credentials()
        results = {first}
        for _ in range(5):
            reset_ap_credentials()
            results.add(generate_ap_credentials())
        assert len(results) > 1


class TestCreateAp:
    """Tests for create_ap."""

    def test_creates_profile_when_missing(self):
        with patch("server.access_point._run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")  # profile list: empty
            result = create_ap("Fotobox-1234", "MyPass012")

        assert result is True
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("add" in cmd for cmd in commands)
        assert any("up" in cmd for cmd in commands)
        # Kein delete mehr – Profile werden wiederverwendet
        assert not any("delete" in cmd for cmd in commands)

    def test_reuses_existing_profile_with_modify(self):
        with patch("server.access_point._run") as mock_run:
            mock_run.return_value = MagicMock(stdout="fotobox-ap\nother\n")
            result = create_ap("Fotobox-1234", "MyPass012")

        assert result is True
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("modify" in cmd for cmd in commands)
        assert not any("add" in cmd for cmd in commands)

    def test_second_call_with_same_credentials_is_cheap(self):
        """Gleiche Credentials + AP aktiv → kein einziger nmcli-Aufruf."""
        with patch("server.access_point._run") as mock_run:
            mock_run.return_value = MagicMock(stdout="")
            assert create_ap("Fotobox-1234", "MyPass012") is True
            calls_first = mock_run.call_count

            assert create_ap("Fotobox-1234", "MyPass012") is True
            assert mock_run.call_count == calls_first

    def test_invalid_ssid(self):
        assert create_ap("", "MyPass012") is False
        assert create_ap("x" * 33, "MyPass012") is False

    def test_short_password(self):
        assert create_ap("Fotobox-1", "short") is False

    def test_nmcli_not_found(self):
        with patch("server.access_point._run", side_effect=FileNotFoundError):
            result = create_ap("Fotobox-1234", "MyPass012")
        assert result is False

    def test_nmcli_error(self):
        exc = subprocess.CalledProcessError(1, "nmcli", stderr="error")

        def side_effect(cmd, **kwargs):
            if "add" in cmd:
                raise exc
            return MagicMock(stdout="")

        with patch("server.access_point._run", side_effect=side_effect):
            result = create_ap("Fotobox-1234", "MyPass012")
        assert result is False


class TestStopAp:
    """Tests for stop_ap."""

    def test_stop_only_brings_connection_down(self):
        """stop_ap fährt den AP runter, löscht aber das Profil nicht mehr."""
        with patch("server.access_point._run") as mock_run:
            stop_ap()
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("down" in cmd for cmd in commands)
        assert not any("delete" in cmd for cmd in commands)

    def test_stop_handles_missing_nmcli(self):
        with patch("server.access_point._run", side_effect=FileNotFoundError):
            stop_ap()  # must not raise


class TestRemoveApProfile:
    """Tests for remove_ap_profile."""

    def test_removes_profile(self):
        with patch("server.access_point._run") as mock_run:
            remove_ap_profile()
        commands = [c.args[0] for c in mock_run.call_args_list]
        assert any("delete" in cmd for cmd in commands)

    def test_handles_missing_nmcli(self):
        with patch("server.access_point._run", side_effect=FileNotFoundError):
            remove_ap_profile()  # must not raise
