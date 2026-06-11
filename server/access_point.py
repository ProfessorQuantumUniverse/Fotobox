"""WiFi Access Point management for the Fotobox download flow.

Uses ``nmcli`` to bring up a temporary hotspot so guests can connect and
download their photos directly from the Raspberry Pi.

Performance notes (Pi 3): the nmcli connection profile is created once and
then reused – subsequent sessions only run ``connection up`` / ``down``
instead of deleting and re-adding the profile every time, which avoids
NetworkManager re-parsing its config and re-negotiating the interface.
Credentials are generated once per process and reused for the whole event.
"""

import logging
import secrets
import string
import subprocess
import threading

from server.config import AP_CONNECTION_NAME, AP_IFACE

logger = logging.getLogger(__name__)

_credentials_lock = threading.Lock()
_cached_credentials: tuple[str, str] | None = None

# Tracks whether the nmcli profile has already been created (and with which
# credentials) so repeat sessions can skip the expensive add/modify step.
_profile_credentials: tuple[str, str] | None = None
_ap_active = False


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check, timeout=30)


def generate_ap_credentials() -> tuple[str, str]:
    """Return the (ssid, password) pair for this Fotobox run.

    Generated once per process with a CSPRNG (``secrets``) and then reused:
    guests who connected earlier stay connected, and NetworkManager does not
    have to tear down and recreate the hotspot profile for every session.
    """
    global _cached_credentials
    with _credentials_lock:
        if _cached_credentials is None:
            suffix = "".join(secrets.choice(string.digits) for _ in range(4))
            ssid = f"Fotobox-{suffix}"
            # 12 chars with letters, digits, and punctuation for ~71 bits of entropy
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(secrets.choice(alphabet) for _ in range(12))
            _cached_credentials = (ssid, password)
        return _cached_credentials


def reset_ap_credentials() -> None:
    """Forget the cached credentials (next session gets fresh ones)."""
    global _cached_credentials
    with _credentials_lock:
        _cached_credentials = None


def _profile_exists() -> bool:
    """Check whether the nmcli profile already exists (cheap read-only call)."""
    res = _run(["nmcli", "-t", "-f", "NAME", "connection", "show"], check=False)
    return AP_CONNECTION_NAME in (res.stdout or "").splitlines()


def create_ap(ssid: str, password: str) -> bool:
    """Bring up a WiFi Access Point via nmcli.

    Args:
        ssid: The SSID to broadcast (must be non-empty, max 32 chars).
        password: The WPA2 passphrase (min 8 characters).

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    global _profile_credentials, _ap_active

    if not ssid or len(ssid) > 32:
        logger.error("Invalid SSID: %r", ssid)
        return False
    if len(password) < 8:
        logger.error("Password too short (min 8 characters)")
        return False

    try:
        if _ap_active and _profile_credentials == (ssid, password):
            logger.info("Access point '%s' already active – nothing to do", ssid)
            return True

        if _profile_credentials != (ssid, password):
            if _profile_exists():
                # Reuse the existing profile, only update SSID/PSK.
                _run(["sudo", "nmcli", "connection", "modify", AP_CONNECTION_NAME,
                      "wifi.ssid", ssid,
                      "wifi-sec.psk", password,
                      ])
            else:
                _run(["sudo", "nmcli", "connection", "add",
                      "type", "wifi",
                      "ifname", AP_IFACE,
                      "con-name", AP_CONNECTION_NAME,
                      "autoconnect", "no",
                      "ssid", ssid,
                      "mode", "ap",
                      "ipv4.method", "shared",
                      "wifi-sec.key-mgmt", "wpa-psk",
                      "wifi-sec.psk", password,
                      ])
            _profile_credentials = (ssid, password)

        _run(["sudo", "nmcli", "connection", "up", AP_CONNECTION_NAME])
        _ap_active = True
        logger.info("Access point '%s' started on %s", ssid, AP_IFACE)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to create access point: %s", exc.stderr)
        _profile_credentials = None
        _ap_active = False
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.error("nmcli not usable – cannot create access point (%s)", exc)
        return False


def stop_ap() -> None:
    """Bring down the temporary Access Point (best-effort).

    The connection profile is kept so the next session only needs a cheap
    ``connection up`` instead of recreating the profile from scratch.
    """
    global _ap_active
    try:
        _run(["sudo", "nmcli", "connection", "down", AP_CONNECTION_NAME], check=False)
        _ap_active = False
        logger.info("Access point '%s' stopped", AP_CONNECTION_NAME)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def remove_ap_profile() -> None:
    """Delete the nmcli profile entirely (e.g. on shutdown)."""
    global _profile_credentials, _ap_active
    try:
        _run(["sudo", "nmcli", "connection", "down", AP_CONNECTION_NAME], check=False)
        _run(["sudo", "nmcli", "connection", "delete", AP_CONNECTION_NAME], check=False)
        _profile_credentials = None
        _ap_active = False
        logger.info("Access point profile '%s' removed", AP_CONNECTION_NAME)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
