# holo-border

A holographic-foil window border for [Omarchy](https://omarchy.org) (Hyprland). The focused window gets a
gradient in your theme's colors with thin white and silver glints,
like the shimmer on a holo trading card.

<!-- Add a screen recording here: docs/demo.gif -->

## What it does

- **Theme colors, in hue order.** Your current Omarchy theme's blue, cyan, magenta, yellow and bright blue
  are laid out around the color wheel, with a blended color between each pair of neighbors, so every band
  flows into the next like holo foil. Each window switch picks a random start and direction, drops in a
  couple of thin white glints and doubles a band or two so the widths vary. It regenerates automatically
  when you switch themes.
- **Neighbor fade.** Each band keeps fading into its top/right neighbor's color, one band every
  `shimmer.seconds_per_band` (2 s), costing about 5% of one core in Hyprland at 10 updates a second. `shimmer.continuous = false`
  fades once per window switch instead, then holds still and costs nothing until the next switch.
- **Sweep.** Right after a window switch's fade-in, then every 5-30 s (random, `sweep.interval_min` /
  `interval_max`), a bar of two thin lines (the leading one white, the other 90% white) (70% opacity on
  a dark wallpaper, up to 100% on a bright one) runs along the focused window's border: across the top
  and bottom together, in a random direction (`sweep.sides` adds runs up or down the sides), fading in
  and then out to nothing over `sweep.duration` (1.33 s). The holo shader draws it; the daemon only
  sends its position in the 10th gradient stop, so the bands use 9 colors.
- **Wallpaper brightness.** The generator scores how bright the wallpaper is (mean perceived lightness,
  0 = dark, 1 = bright). That score sets the border opacity (69% on a dark wallpaper up to 100% on a bright
  one), how hard the colors are pushed away from the wallpaper's lightness (contrast target 2.0 up to 4.0),
  and how much extra chroma they get (up to +80%). Dark themes stay soft; bright ones get a stronger border.
- **Same look on every theme.** Unless `colors.raw` is on, colors are made pastel and clamped into a fixed
  OKLCH lightness/chroma band, so a loud theme can't produce a harsh border.
- **Adapts to what is behind it.** Colors close to the wallpaper's dominant color get more chroma and move
  lighter or darker away from it. If the wallpaper changes, the daemon re-samples it. (Needs ImageMagick;
  without it the theme background color is used.)
- **Fixed angle.** The gradient angle is fixed (`border.angle`).
- **Fade in.** Selecting a window fades its border from the inactive grey to the gradient. By default the
  daemon does the fade; with `fade_in.native = true` Hyprland's own border animation does it, which avoids the
  one-or-two-frame flash of full color Hyprland paints before the daemon can react.
- **Opposites.** The white glints start as the color directly across the color wheel from the color before them
  and fade to white.
- **Sticker edge.** A thin dark outline around the focused window, stronger on bright wallpapers
  (`outline`). With it off, the window gets a faint shadow tinted from the gradient instead.
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
| `border.size`, `border.angle`, `border.alpha` | width in px, opacity (used when `transparency.enabled` is off) |
| `colors.chroma_max` / `chroma_min` | how vivid the colors can be |
| `colors.lightness_min` / `lightness_max` | how pale or deep the colors can be |
| `adaptive.source`, `high` / `low`, `max_boost`, `lightness_push` | what to compare against (`wallpaper` or `theme`), the distance range, and how strong the boost is |
| `fade_in.updates_per_second` | update rate while a fade runs (match the screen refresh); nothing is sent otherwise |
| `fade_in.duration` / `native` | seconds for the grey-to-gradient fade, and whether Hyprland (`true`) or the daemon (`false`) does it |
| `bands.colors`, `highlights`, `wide` | colored stops, white glints, and how many bands may be doubled (keep colors + highlights at 10 or less) |
| `shimmer.enabled`, `seconds_per_band`, `updates_per_second` | the band-to-band fade, its speed, and its update rate |
| `sweep.enabled`, `on_switch`, `interval_min` / `interval_max`, `duration`, `width`, `lines` / `line_gap` / `line_grey`, `distance`, `opacity_dark` / `opacity_bright`, `fade_in`, `sides` | the sweep: whether one runs after each switch's fade-in, the range of seconds between sweeps, how long one runs, its bar length, how many lines it's made of, the gap between them and how grey the outer ones are, how far it travels (fractions of the edge), its peak white opacity on a dark and a bright wallpaper, how much of the run it spends fading in, and whether it can run along the sides |
| `outline.enabled`, `range`, `min_alpha` / `max_alpha` | the dark sticker edge, its width, and its opacity on dark / bright wallpapers |
| `opposites.fade` | seconds for the silvers to fade back from their opposite color |
| `shadow.range` / `alpha` / `render_power` | size, opacity and softness of the focused-window shadow |
| `transparency.min_alpha` / `max_alpha` | border opacity on a dark and a bright wallpaper |
| `transparency.solid_above` | a wallpaper scoring above this gets a fully opaque border |
| `transparency.dark_l` / `bright_l` | wallpaper lightness that scores 0 and 1 |
| `legibility.target_dark` / `target_bright` | contrast the colors must reach against a dark / bright wallpaper |
| `vividness.max_boost` | extra chroma on a bright wallpaper |
| `colors.raw` | use the theme's exact colors, with no pastel, clamp or wallpaper adjust |

## How it works

`gen-holo-border.py` turns the theme's `colors.toml` into a gradient and writes it where Hyprland loads it.
`drift.py` (the name is historical; the gradient no longer drifts) is a small daemon that listens for
Hyprland's focus events. When you select a window it sends Hyprland a fresh random arrangement of the colors and,
for about half a second, 60 updates a second to run the fade and the opposite-color flash. The rest of the time
it sends nothing. If Hyprland reloads its config (a theme or wallpaper change) it sends the border again.

Cost: with the border on and idle, Hyprland uses no more CPU than with the border off. A window switch costs a
short burst.

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
