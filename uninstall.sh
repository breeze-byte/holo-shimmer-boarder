#!/bin/bash
# Remove holo-border. Pass --purge to also delete your config.toml.
#   ./uninstall.sh [--purge]
set -euo pipefail

HYPR="$HOME/.config/hypr"
PURGE=0
[[ ${1:-} == --purge ]] && PURGE=1

# Turn it off first (stops the daemon, restores Omarchy's border).
if [[ -x $HOME/.local/bin/holo ]]; then
  "$HOME/.local/bin/holo" off || true
fi

# Remove the marked blocks from the Hyprland config files.
for f in looknfeel.lua autostart.lua bindings.lua; do
  if [[ -f $HYPR/$f ]] && grep -q ">>> holo-border" "$HYPR/$f"; then
    sed -i '/-- >>> holo-border/,/-- <<< holo-border/d' "$HYPR/$f"
    echo "unwired: $f"
  fi
done

rm -f "$HOME/.local/bin/holo" "$HOME/.config/omarchy/hooks/theme-set.d/holo-border.sh" "$HYPR/holo-border.lua"
rm -rf "$HOME/.local/state/holo"
if [[ $PURGE == 1 ]]; then
  rm -rf "$HYPR/holo"
else
  rm -f "$HYPR"/holo/*.py
  rm -rf "$HYPR"/holo/__pycache__
  echo "kept $HYPR/holo/config.toml (use --purge to delete it)"
fi

[[ -n ${HOLO_NO_HYPRCTL:-} ]] || hyprctl reload >/dev/null 2>&1 || true
echo "holo-border removed."
