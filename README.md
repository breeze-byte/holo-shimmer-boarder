# holo-border

A holographic-foil window border for [Omarchy](https://omarchy.org) (Hyprland). The focused window gets a
slowly drifting gradient in your theme's colors with thin white and silver glints,
like the shimmer on a holo trading card.

<!-- Add a screen recording here: docs/demo.gif -->

## What it does

- **Theme colors.** The gradient is built from three of your current Omarchy theme's blue, cyan, magenta,
  yellow and bright blue, picked and ordered at random on every window switch, with a silver between each
  and white at both ends. It regenerates automatically when you switch themes.
- **Wallpaper brightness.** The generator scores how bright the wallpaper is (mean perceived lightness,
  0 = dark, 1 = bright). That score sets the border opacity (38% on a dark wallpaper up to 100% on a bright
  one), how hard the colors are pushed away from the wallpaper's lightness (contrast target 2.0 up to 4.0),
  and how much extra chroma they get (up to +80%). Dark themes stay soft; bright ones get a stronger border.
- **Same look on every theme.** Unless `colors.raw` is on, colors are made pastel and clamped into a fixed
  OKLCH lightness/chroma band, so a loud theme can't produce a harsh border.
- **Adapts to what is behind it.** Colors close to the wallpaper's dominant color get more chroma and move
  lighter or darker away from it. If the wallpaper changes, the daemon re-samples it. (Needs ImageMagick;
  without it the theme background color is used.)
- **Drift.** The gradient angle wanders very slowly and reverses direction every few seconds.
- **Settle.** After a few idle seconds the drift slows to a third of its speed.
- **Fade in.** Selecting a window fades its border from the inactive grey to the gradient. By default the
  daemon does the fade; with `fade_in.native = true` Hyprland's own border animation does it, which avoids the
  one-or-two-frame flash of full color Hyprland paints before the daemon can react.
- **Opposites.** The silver stops start as the color directly across the color wheel from the color before them
  and fade back to silver.
- **Shadow.** The focused window gets a faint shadow tinted from the gradient, fading in with the border.
- **On/off toggle.** One command or keybind; off restores Omarchy's normal border.

## Requirements

- Omarchy with the **Lua Hyprland config** (`~/.config/hypr/{hyprland,looknfeel,autostart,bindings}.lua`)
- Python 3.11+ (uses `tomllib`)
- ImageMagick (`magick`) to sample the wallpaper (optional; falls back to the theme background)
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
| `border.size`, `border.alpha` | width in px, opacity (used when `transparency.enabled` is off) |
| `colors.chroma_max` / `chroma_min` | how vivid the colors can be |
| `colors.lightness_min` / `lightness_max` | how pale or deep the colors can be |
| `adaptive.source`, `high` / `low`, `max_boost`, `lightness_push` | what to compare against (`wallpaper` or `theme`), the distance range, and how strong the boost is |
| `drift.min_speed` / `max_speed` | degrees per second |
| `drift.leg_min` / `leg_max` | seconds before it reverses direction |
| `drift.updates_per_second` / `idle_updates_per_second` | update rate while a switch is fading (60 matches a 60 Hz screen) and once it has settled (the slow drift needs far less) |
| `settle.after` / `settle.factor` | when and how much it slows down |
| `fade_in.duration` / `native` | seconds for the grey-to-gradient fade, and whether Hyprland (`true`) or the daemon (`false`) does it |
| `bands.colors` | how many theme colors are in the gradient (of 5) |
| `opposites.fade` | seconds for the silvers to fade back from their opposite color |
| `shadow.range` / `alpha` / `render_power` | size, opacity and softness of the focused-window shadow |
| `transparency.min_alpha` / `max_alpha` | border opacity on a dark and a bright wallpaper |
| `transparency.dark_l` / `bright_l` | wallpaper lightness that scores 0 and 1 |
| `legibility.target_dark` / `target_bright` | contrast the colors must reach against a dark / bright wallpaper |
| `vividness.max_boost` | extra chroma on a bright wallpaper |
| `colors.raw` | use the theme's exact colors, with no pastel, clamp or wallpaper adjust |

## How it works

Hyprland caps its built-in border animation at about 10 seconds per turn and can't randomize or react
to focus changes. So `drift.py` is a small daemon that sets the gradient angle itself over Hyprland's
command socket, 60 times a second, and listens for focus events. `gen-holo-border.py`
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
