#!/usr/bin/env bash
# Fotobox – USB-Stick automatisch mounten (headless, ohne Desktop).
#
# Auf einem Pi ohne Desktop gibt es keinen Automounter: ein eingesteckter
# Stick (z. B. /dev/sda1) bleibt einfach ungemountet, und die Fotobox findet
# ihn nie. Dieses Skript richtet die komplette Auto-Mount-Kette ein:
#
#   udev-Regel  --(beim Ein-/Ausstecken)-->  systemd-Service  -->  mount-Skript
#
# Jeder eingesteckte USB-Stick wird nach  /media/usb-<dev>  gemountet, und zwar
# mit den Schreibrechten des fotobox-Users (sonst meldet die Fotobox den Stick
# nicht, weil sie nicht darauf schreiben darf). Funktioniert mit FAT32, exFAT,
# NTFS und ext4 – auch im laufenden Betrieb.
#
# Einmalig ausführen:   sudo ./setup-usb-automount.sh
#
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Bitte mit sudo ausführen:  sudo ./setup-usb-automount.sh" >&2
  exit 1
fi

FOTOBOX_USER="${FOTOBOX_USER:-fotobox}"
if ! id -u "$FOTOBOX_USER" >/dev/null 2>&1; then
  echo "Benutzer '$FOTOBOX_USER' existiert nicht. Setze FOTOBOX_USER=<name> und erneut starten." >&2
  exit 1
fi

WORKER=/usr/local/sbin/fotobox-usb-mount.sh
UDEV_RULE=/etc/udev/rules.d/99-fotobox-usb.rules
MOUNT_UNIT=/etc/systemd/system/fotobox-usb-mount@.service
UMOUNT_UNIT=/etc/systemd/system/fotobox-usb-umount@.service

echo "=== Fotobox USB-Auto-Mount einrichten (User: $FOTOBOX_USER) ==="

# --- 1) Worker-Skript: mountet/unmountet ein einzelnes Gerät ----------------
cat > "$WORKER" <<EOF
#!/usr/bin/env bash
# Wird von udev/systemd aufgerufen:  fotobox-usb-mount.sh <add|remove> <devbase>
# <devbase> ist z. B. "sda1". Mountet nach /media/usb-<devbase>.
set -u

ACTION="\${1:-}"
DEVBASE="\${2:-}"
[ -z "\$DEVBASE" ] && exit 0
DEVICE="/dev/\${DEVBASE}"
MOUNT_POINT="/media/usb-\${DEVBASE}"
FOTOBOX_USER="${FOTOBOX_USER}"
UID_N="\$(id -u "\$FOTOBOX_USER")"
GID_N="\$(id -g "\$FOTOBOX_USER")"

log() { logger -t fotobox-usb "\$*"; }

do_mount() {
  # Schon gemountet? Dann nichts tun.
  findmnt -rno TARGET "\$DEVICE" >/dev/null 2>&1 && exit 0
  mkdir -p "\$MOUNT_POINT"
  # Dateisystemtyp ermitteln (setzt TYPE=, LABEL=, UUID=).
  eval "\$(blkid -o export "\$DEVICE" 2>/dev/null)"
  case "\${TYPE:-}" in
    vfat|exfat)
      mount -o "uid=\${UID_N},gid=\${GID_N},umask=000" "\$DEVICE" "\$MOUNT_POINT" ;;
    ntfs)
      mount -t ntfs-3g -o "uid=\${UID_N},gid=\${GID_N},umask=000" "\$DEVICE" "\$MOUNT_POINT" ;;
    ext2|ext3|ext4)
      mount "\$DEVICE" "\$MOUNT_POINT" && chown "\${UID_N}:\${GID_N}" "\$MOUNT_POINT" ;;
    "")
      log "kein Dateisystem auf \$DEVICE – ignoriert"; rmdir "\$MOUNT_POINT" 2>/dev/null; exit 0 ;;
    *)
      mount "\$DEVICE" "\$MOUNT_POINT" 2>/dev/null || { rmdir "\$MOUNT_POINT" 2>/dev/null; exit 0; } ;;
  esac
  log "\$DEVICE (\${TYPE:-?}) gemountet nach \$MOUNT_POINT"
}

do_unmount() {
  if findmnt -rno TARGET "\$MOUNT_POINT" >/dev/null 2>&1; then
    umount -l "\$MOUNT_POINT" && log "\$MOUNT_POINT ausgehängt"
  fi
  rmdir "\$MOUNT_POINT" 2>/dev/null || true
}

case "\$ACTION" in
  add)    do_mount ;;
  remove) do_unmount ;;
  *)      exit 0 ;;
esac
EOF
chmod 0755 "$WORKER"
echo "  -> $WORKER"

# --- 2) systemd-Service-Templates -------------------------------------------
cat > "$MOUNT_UNIT" <<EOF
[Unit]
Description=Fotobox: USB-Stick %i einhängen
[Service]
Type=oneshot
RemainAfterExit=true
ExecStart=$WORKER add %i
EOF
echo "  -> $MOUNT_UNIT"

cat > "$UMOUNT_UNIT" <<EOF
[Unit]
Description=Fotobox: USB-Stick %i aushängen
[Service]
Type=oneshot
ExecStart=$WORKER remove %i
EOF
echo "  -> $UMOUNT_UNIT"

# --- 3) udev-Regel ----------------------------------------------------------
# Nur Partitionen (sd?1) auf echten USB-Geräten. Beim Einstecken mounten,
# beim Abziehen aushängen.
cat > "$UDEV_RULE" <<'EOF'
ACTION=="add",    KERNEL=="sd[a-z][0-9]", SUBSYSTEMS=="usb", ENV{SYSTEMD_WANTS}+="fotobox-usb-mount@%k.service"
ACTION=="remove", KERNEL=="sd[a-z][0-9]", ENV{SYSTEMD_WANTS}+="fotobox-usb-umount@%k.service"
EOF
echo "  -> $UDEV_RULE"

# --- 4) Neu laden -----------------------------------------------------------
systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger --subsystem-match=block --action=add

echo ""
echo "Fertig. Steck den Stick (neu) ein – er landet automatisch unter"
echo "  /media/usb-<gerät>   (z. B. /media/usb-sda1)"
echo "und die Fotobox sichert die Fotos dorthin (Toast erscheint)."
echo ""
echo "Schon steckenden Stick jetzt sofort mounten (ohne Aus-/Einstecken):"
echo "  sudo udevadm trigger --subsystem-match=block --action=add"
echo ""
echo "Prüfen:   findmnt /media/usb-*   bzw.   journalctl -t fotobox-usb"
