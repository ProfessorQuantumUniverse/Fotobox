"""WiFi Access Point management for the Fotobox download flow.

Uses ``nmcli`` to create and tear down a temporary hotspot so guests can
connect and download their photos directly from the Raspberry Pi.
"""

import logging
import random
import string
import subprocess

from server.config import AP_CONNECTION_NAME, AP_IFACE

logger = logging.getLogger(__name__)


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def generate_ap_credentials() -> tuple[str, str]:
    """Return a randomised (ssid, password) pair for a new hotspot session."""
    suffix = "".join(random.choices(string.digits, k=4))
    ssid = f"Fotobox-{suffix}"
    # 12 chars with letters, digits, and punctuation for ~71 bits of entropy
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(random.choices(alphabet, k=12))
    return ssid, password


def create_ap(ssid: str, password: str) -> bool:
    """Bring up a WiFi Access Point via nmcli.

    Args:
        ssid: The SSID to broadcast (must be non-empty, max 32 chars).
        password: The WPA2 passphrase (min 8 characters).

    Returns:
        ``True`` on success, ``False`` otherwise.
    """
    if not ssid or len(ssid) > 32:
        logger.error("Invalid SSID: %r", ssid)
        return False
    if len(password) < 8:
        logger.error("Password too short (min 8 characters)")
        return False
    # Remove any leftover connection with the same name (best-effort).
    try:
        _run(["nmcli", "connection", "delete", AP_CONNECTION_NAME], check=False)
    except FileNotFoundError:
        logger.error("nmcli not found – cannot create access point")
        return False

    # "sudo" vor nmcli setzen
    try:
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
        _run(["sudo", "nmcli", "connection", "up", AP_CONNECTION_NAME])
        logger.info("Access point '%s' started on %s", ssid, AP_IFACE)
        return True
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to create access point: %s", exc.stderr)
        return False
    except FileNotFoundError:
        logger.error("nmcli not found – cannot create access point")
        return False


def stop_ap() -> None:
    """Bring down and remove the temporary Access Point (best-effort)."""
    try:
        _run(["nmcli", "connection", "down", AP_CONNECTION_NAME], check=False)
        _run(["nmcli", "connection", "delete", AP_CONNECTION_NAME], check=False)
        logger.info("Access point '%s' stopped", AP_CONNECTION_NAME)
    except FileNotFoundError:
        pass
