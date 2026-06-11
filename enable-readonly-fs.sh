#!/usr/bin/env bash
# Fotobox – Root-Dateisystem read-only machen (Overlay FS).
#
# Danach kann der Pi jederzeit hart vom Strom getrennt werden, ohne dass die
# SD-Karte oder die Services beschädigt werden: alle Schreibzugriffe auf "/"
# landen nur noch in einem RAM-Overlay und sind nach dem Neustart wieder weg.
#
# WICHTIG – Konsequenzen:
#   * Lokale Fotos in ~/photos überleben einen Neustart NICHT. Deshalb IMMER
#     einen USB-Stick stecken – Fotos werden dorthin gesichert (FOTOBOX_USB_BACKUP).
#   * Code-Änderungen am Pi (git pull o. Ä.) überleben einen Neustart nicht,
#     solange das Overlay aktiv ist. Zum Aktualisieren erst Overlay deaktivieren.
#
# Overlay später wieder ausschalten (z. B. zum Aktualisieren):
#   sudo raspi-config nonint disable_overlayfs && sudo reboot
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Bitte mit sudo ausführen:  sudo ./enable-readonly-fs.sh" >&2
  exit 1
fi

if ! command -v raspi-config >/dev/null 2>&1; then
  echo "raspi-config nicht gefunden – dieses Skript ist nur für Raspberry Pi OS." >&2
  exit 1
fi

echo "=== Overlay-Dateisystem aktivieren (Root read-only) ==="
# Boot-Partition read-only + Overlay aufs Root-FS legen.
raspi-config nonint enable_overlayfs

echo ""
echo "Fertig. Nach dem Neustart ist '/' read-only und Steckerziehen ist sicher."
echo "  -> Fotos NUR noch auf USB-Stick verlassen sich (Stick stecken lassen!)."
echo "  -> Zum Aktualisieren: sudo raspi-config nonint disable_overlayfs && sudo reboot"
echo ""
read -r -p "Jetzt neu starten? [j/N] " ans
case "$ans" in
  j|J|y|Y) reboot ;;
  *) echo "Bitte später manuell neu starten: sudo reboot" ;;
esac
