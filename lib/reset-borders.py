#!/usr/bin/env python3
"""Put every window's active border back to Hyprland's configured one (used when holo is off).

While on, holo sets each focused window's own active_border_color (much cheaper than changing the
config). Hyprland 0.56 has no way to clear that per-window value ("unset" leaves the last color
drawn), so instead it's set to the configured col.active_border, read back from Hyprland. Run it
after the config is reloaded, and again after a theme change while holo is off.
"""
import json, subprocess, sys

def hyprctl(*args):
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5).stdout

def main():
    # "gradient data: ffdcd7ba ff7aa89f 45deg" (AARRGGBB colors, then the angle)
    words = hyprctl("getoption", "general:col.active_border").split("\n")[0].split(":", 1)[-1].split()
    colors = ["rgba(%s%s)" % (w[2:], w[:2]) for w in words if len(w) == 8 and all(c in "0123456789abcdef" for c in w)]
    angle = next((w for w in words if w.endswith("deg")), "0deg")
    if not colors:
        sys.exit("reset-borders: couldn't read general:col.active_border")
    # Hyprland 0.56's set_prop drops a gradient value's first color, so lead with a throwaway one.
    value = "rgba(00000000) " + " ".join(colors) + " " + angle
    for c in json.loads(hyprctl("clients", "-j") or "[]"):
        hyprctl("dispatch", 'hl.dsp.window.set_prop({ prop = "active_border_color", value = "%s", window = "address:%s" })'
                % (value, c["address"]))

if __name__ == "__main__":
    main()
