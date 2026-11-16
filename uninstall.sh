#!/usr/bin/env bash
set -euo pipefail
PREFIX="${PREFIX:-$HOME/.local}"
systemctl --user stop seiren-emote-restore.service 2>/dev/null || true
rm -rf "$PREFIX/share/seiren-emote" "$PREFIX/bin/emote" \
       "$PREFIX/share/applications/seiren-emote.desktop" \
       "$HOME/.config/systemd/user/seiren-emote-restore.service"
systemctl --user daemon-reload 2>/dev/null || true
if ls /etc/udev/rules.d/*-razer-seiren-emote.rules >/dev/null 2>&1; then
  sudo rm -f /etc/udev/rules.d/70-razer-seiren-emote.rules /etc/udev/rules.d/99-razer-seiren-emote.rules
  sudo udevadm control --reload-rules
fi
echo "Removed. (Your saved image in ~/.config/seiren-emote was kept.)"
