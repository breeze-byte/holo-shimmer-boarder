#!/usr/bin/env python3
"""Pick the holo palette: palette.py next | prev | get | list | <name>

Saves the choice in ~/.local/state/holo/palette (it overrides colors.palette in config.toml)
and prints its label. bin/holo regenerates the colors afterwards.
"""
import os, sys

import holo_config

names = list(holo_config.PALETTES)
current = holo_config.palette(holo_config.load())
arg = sys.argv[1] if len(sys.argv) > 1 else "next"

if arg == "list":
    for n in names:
        print(("* " if n == current else "  ") + n.ljust(16) + holo_config.PALETTES[n])
    sys.exit()
if arg == "get":
    print(holo_config.PALETTES.get(current, current))
    sys.exit()
if arg in ("next", "prev"):
    i = names.index(current) if current in names else -1
    new = names[(i + (1 if arg == "next" else -1)) % len(names)]
elif arg in names or arg == "theme":
    new = arg
else:
    print("unknown palette: %s (one of: %s)" % (arg, ", ".join(names)), file=sys.stderr)
    sys.exit(1)

os.makedirs(os.path.dirname(holo_config.PALETTE_STATE), exist_ok=True)
open(holo_config.PALETTE_STATE, "w").write(new + "\n")
print(holo_config.PALETTES.get(new, new))
