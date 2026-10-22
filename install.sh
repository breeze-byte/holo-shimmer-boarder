#!/bin/bash
# Install holo-border for Omarchy (Hyprland Lua config).
#   ./install.sh [--key "SUPER + SHIFT + H"] [--no-keybind] [--no-activate]
# Safe to run more than once. Each file it edits is backed up once as
# <file>.holo-install.bak, and the lines it adds sit between
# ">>> holo-border" / "<<< holo-border" markers so uninstall.sh can remove them.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HYPR="$HOME/.config/hypr"
LIB="$HYPR/holo"
BIN="$HOME/.local/bin"
HOOKS="$HOME/.config/omarchy/hooks/theme-set.d"
KEY="SUPER + SHIFT + H"
KEYBIND=1
ACTIVATE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --key) KEY="$2"; shift 2 ;;
    --no-keybind) KEYBIND=0; shift ;;
    --no-activate) ACTIVATE=0; shift ;;
    -h|--help) sed -n 2,6p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

# --- requirements ---
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null \
  || die "Python 3.11+ is required (for tomllib)."
[[ $ACTIVATE == 0 ]] || command -v hyprctl >/dev/null || die "hyprctl not found: is Hyprland running?"
for f in hyprland.lua looknfeel.lua autostart.lua bindings.lua; do
  [[ -f $HYPR/$f ]] || die "$HYPR/$f not found. This needs Omarchy's Lua Hyprland config."
done
[[ -f $HOME/.local/state/omarchy/current/theme/colors.toml ]] \
  || die "No current Omarchy theme found (~/.local/state/omarchy/current/theme/colors.toml)."
case ":$PATH:" in *":$BIN:"*) ;; *) echo "note: $BIN is not on your PATH; the keybind and autostart use the full path." ;; esac

# --- files ---
mkdir -p "$LIB" "$BIN" "$HOOKS" "$HOME/.local/state/holo"
cp "$HERE"/lib/*.py "$LIB/"
mkdir -p "$LIB/shaders" && cp "$HERE"/lib/shaders/* "$LIB/shaders/"
chmod +x "$LIB/gen-holo-border.py" "$LIB/drift.py"
[[ -f $LIB/config.toml ]] || cp "$HERE/config.toml" "$LIB/config.toml"
cp "$HERE/bin/holo" "$BIN/holo"; chmod +x "$BIN/holo"
cp "$HERE/hooks/holo-border.sh" "$HOOKS/holo-border.sh"
[[ -f $HYPR/holo-border.lua ]] || echo "-- holo border is off (run: holo on)" >"$HYPR/holo-border.lua"  # replaced by "holo on" below

# --- wiring: append a marked block to a Hyprland config file, once ---
add_block() {  # file, content
  local file="$1" content="$2"
  if grep -q ">>> holo-border" "$file"; then
    echo "already wired: $(basename "$file")"
    return
  fi
  [[ -f $file.holo-install.bak ]] || cp "$file" "$file.holo-install.bak"
  printf '\n-- >>> holo-border (added by holo-border install.sh) >>>\n%s\n-- <<< holo-border <<<\n' "$content" >>"$file"
  echo "wired: $(basename "$file")"
}

add_block "$HYPR/looknfeel.lua" 'pcall(require, "hypr.holo-border")'
add_block "$HYPR/autostart.lua" "hl.on(\"hyprland.start\", function()
  hl.exec_cmd(\"$BIN/holo start\")
end)"
if [[ $KEYBIND == 1 ]]; then
  add_block "$HYPR/bindings.lua" "o.bind(\"$KEY\", \"Toggle holo border\", \"$BIN/holo toggle\")"
fi

# --- turn it on ---
if [[ $ACTIVATE == 1 ]]; then
  "$BIN/holo" on
  if [[ $KEYBIND == 1 ]]; then
    echo "holo border is on. Toggle it with: holo toggle  (or $KEY)"
  else
    echo "holo border is on. Toggle it with: holo toggle"
  fi
else
  touch "$HOME/.local/state/holo/enabled"
  HOLO_NO_HYPRCTL=1 "$BIN/holo" on
  echo "installed. Reload Hyprland (hyprctl reload) and run: holo restart"
fi
