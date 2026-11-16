#!/usr/bin/env bash
# Installs seiren-emote for the current user (+ one udev rule, which needs sudo).
set -euo pipefail
cd "$(dirname "$0")"

PREFIX="${PREFIX:-$HOME/.local}"
BINDIR="$PREFIX/bin"
SHARE="$PREFIX/share/seiren-emote"
PY=/usr/bin/python3
[ -x "$PY" ] || PY="$(command -v python3)"

echo "==> Checking dependencies"
missing=0
for mod in usb PIL gi cairo; do
  "$PY" -c "import $mod" 2>/dev/null || { echo "    missing python module: $mod"; missing=1; }
done
"$PY" -c "import gi; gi.require_version('Gtk','4.0')" 2>/dev/null || { echo "    missing GTK 4 bindings"; missing=1; }
if [ "$missing" = 1 ]; then
  if command -v apt-get >/dev/null; then
    echo "==> Installing dependencies with apt (needs sudo)"
    sudo apt-get install -y python3-usb python3-pil python3-gi python3-gi-cairo gir1.2-gtk-4.0
  elif command -v dnf >/dev/null; then
    sudo dnf install -y python3-pyusb python3-pillow python3-gobject python3-cairo gtk4
  elif command -v pacman >/dev/null; then
    sudo pacman -S --needed python-pyusb python-pillow python-gobject python-cairo gtk4
  else
    echo "Please install: pyusb, Pillow, PyGObject, GTK 4 — then re-run." >&2
    exit 1
  fi
fi

echo "==> Installing program to $SHARE"
rm -rf "$SHARE"
mkdir -p "$SHARE" "$BINDIR"
cp -r seiren_emote "$SHARE/"
cp data/seiren-emote.svg "$SHARE/"

cat > "$BINDIR/emote" <<EOF
#!/bin/sh
PYTHONPATH="$SHARE\${PYTHONPATH:+:\$PYTHONPATH}" exec "$PY" -m seiren_emote "\$@"
EOF
chmod +x "$BINDIR/emote"

echo "==> Adding app menu entry"
mkdir -p "$PREFIX/share/applications"
sed -e "s|@BINDIR@|$BINDIR|" -e "s|@ICON@|$SHARE/seiren-emote.svg|" \
  data/seiren-emote.desktop > "$PREFIX/share/applications/seiren-emote.desktop"

echo "==> Installing restore-on-plug-in service"
mkdir -p "$HOME/.config/systemd/user"
sed "s|@BINDIR@|$BINDIR|" data/seiren-emote-restore.service \
  > "$HOME/.config/systemd/user/seiren-emote-restore.service"
systemctl --user daemon-reload 2>/dev/null || true

echo "==> Installing udev rule (needs sudo) so no root is needed to use the mic"
sudo rm -f /etc/udev/rules.d/99-razer-seiren-emote.rules  # old name, didn't work
sudo install -m 644 data/70-razer-seiren-emote.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=1532

echo
echo "Done! Unplug and replug the mic once, then:"
echo "  emote gui           # open the app (also in your app menu as 'Seiren Emote')"
echo "  emote preset smile  # or use the command line"
case ":$PATH:" in *":$BINDIR:"*) ;; *) echo "Note: $BINDIR is not on your PATH; add it or run $BINDIR/emote";; esac
