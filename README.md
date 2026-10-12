# holo-border

A holographic-foil window border for [Omarchy](https://omarchy.org) (Hyprland). The focused window gets a
slowly drifting gradient in your theme's colors with thin white and silver glints,
like the shimmer on a holo trading card.

<!-- Add a screen recording here: docs/demo.gif -->

## What it does

- **Theme colors.** The gradient is built from your current Omarchy theme's blue, cyan, magenta,
  yellow and bright blue. It regenerates automatically when you switch themes.
- **Same contrast on every theme.** Colors are clamped into a fixed OKLCH lightness/chroma band, so a
  loud theme can't produce a harsh border.
- **Adapts to the background.** If a theme's background is muted (low contrast with the border), the
  colors get more chroma and move lighter/darker away from the background. High-contrast themes are
  left exactly as they are, and the boost scales smoothly in between.
- **Drift.** The gradient angle wanders smoothly and reverses direction every few seconds.
- **Tilt.** Where your cursor sits inside the focused window shifts the gradient, like tilting a card.
- **Settle.** After a few idle seconds the drift slows to a third of its speed.
- **Flash.** Selecting a window briefly shows the theme's complementary colors, which fade back.
- **On/off toggle.** One command or keybind; off restores Omarchy's normal border.

## Requirements

- Omarchy with the **Lua Hyprland config** (`~/.config/hypr/{hyprland,looknfeel,autostart,bindings}.lua`)
- Python 3.11+ (uses `tomllib`)
- Hyprland 0.56 or newer (developed on 0.56.2)

Tested on dark themes (Kanagawa, Matte Black). Light themes are supported, but I haven't looked at
them on screen.

## Install

```bash
git clone <this repo> holo-border
cd holo-border
./install.sh
```

Options: `--key "SUPER + SHIFT + H"` (change the toggle keybind), `--no-keybind`, `--no-activate`.

The installer copies the scripts into `~/.config/hypr/holo/` and `~/.local/bin/holo`, adds a theme hook,
and appends a small marked block to `looknfeel.lua`, `autostart.lua` and `bindings.lua` (each file is
backed up once as `*.holo-install.bak`). It is safe to run twice.

## Use

```
holo toggle      # or Super+Shift+H
holo on | off
holo status
holo restart     # after editing config.toml
holo refresh     # regenerate colors (the theme hook does this for you)
```

The on/off choice persists across reboots and theme changes.

## Configure

Edit `~/.config/hypr/holo/config.toml`, then run `holo restart`. Common tweaks:

| Setting | Effect |
|---|---|
| `border.size`, `border.alpha` | width in px, opacity |
| `colors.chroma_max` / `chroma_min` | how vivid the colors can be |
| `colors.lightness_min` / `lightness_max` | how pale or deep the colors can be |
| `adaptive.high` / `low` / `max_boost` | the background-contrast range and how strong the boost gets |
| `drift.min_speed` / `max_speed` | degrees per second |
| `drift.leg_min` / `leg_max` | seconds before it reverses direction |
| `drift.updates_per_second` | smoothness vs. CPU |
| `tilt.x` / `tilt.y` | how far the cursor tilts the gradient |
| `settle.after` / `settle.factor` | when and how much it slows down |
| `flash.hold` / `flash.fade` | how long the complementary colors last |

## How it works

Hyprland caps its built-in border animation at about 10 seconds per turn and can't randomize or react
to the mouse. So `drift.py` is a small daemon that sets the gradient angle itself over Hyprland's
command socket, 20 times a second, using the cursor position and the focused window. `gen-holo-border.py`
turns the theme's `colors.toml` into the gradient and writes it where Hyprland loads it.

Cost: Hyprland re-parses the config on every update, so expect a few percent of one CPU core while
the border is animating. Lower `drift.updates_per_second` to reduce it.

## Limitations

- Hyprland gives each window one border band, so there are no separate inner and outer lines. The
  `borders-plus-plus` plugin can add lines, but only as flat colors, on every window, outside the border.
- Only the focused window's border animates.
- Developed and tested on one machine. Reports and fixes are welcome.

## Uninstall

```bash
./uninstall.sh          # keeps your config.toml
./uninstall.sh --purge  # removes it too
```

## License

MIT
