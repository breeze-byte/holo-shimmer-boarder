# holo-border

A holographic-foil window border for [Omarchy](https://omarchy.org) (Hyprland). The focused window gets a
pastel-rainbow gradient sampled from a holographic sticker, with white glints and a soft sweep of light,
like the shimmer on a holo trading card.

<!-- Add a screen recording here: docs/demo.gif -->

## What it does

- **Sticker colors, in hue order.** Ten colors sampled from a holographic sticker's foil (pink, peach,
  butter, mint, aqua, sky, periwinkle, lavender, violet, orchid) are laid out around the color wheel,
  with a blended color between each pair of neighbors, so every band flows into the next like holo foil.
  They're the same on every theme and keep their own lightness; on a brighter wallpaper they get a
  little more saturation (`colors.sticker_boost`) so they don't look washed out. `colors.palette =
  "theme"` uses your Omarchy theme's blue, cyan, magenta, yellow and bright blue instead, regenerated
  whenever you switch themes. Each window switch picks a random start.
- **Neighbor fade.** Each band keeps fading into its top/right neighbor's color, one band every
  `shimmer.seconds_per_band` (2 s), costing about 5% of one core in Hyprland at 10 updates a second. `shimmer.continuous = false`
  fades once per window switch instead, then holds still and costs nothing until the next switch.
- **Sweep.** When you switch windows, 0.02 s later a soft highlight (a bell curve of light that
  brightens each band's own color, `sweep.style = "glow"`; `"bars"` draws hard white lines instead) runs
  across the top and bottom of the new window's border, away from the window you came from, in a single
  pass (`sweep.bounce` adds a drift back at the end). When you switch workspaces it runs up the sides
  and back down instead (`sweep.workspace`). It fades in and then out to nothing as it crosses, over
  `sweep.duration` (0.99 s). Its peak opacity follows the wallpaper (95% on a dark one, up to 100% on a
  bright one). `sweep.periodic` adds random repeats every 5-30 s. The holo shader draws it; the daemon
  only sends its position in the 10th gradient stop, so the bands use 9 colors.
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
| `colors.sticker_boost` / `sticker_boost_from` | sticker palette: extra saturation on a bright wallpaper, ramping up from the given brightness |
| `colors.palette` | `sticker` (default: the holo sticker's pastel rainbow, the same on every theme) or `theme` (the Omarchy theme's colors) |
| `border.size`, `border.angle`, `border.alpha` | width in px, opacity (used when `transparency.enabled` is off) |
| `colors.chroma_max` / `chroma_min` | how vivid the colors can be |
| `colors.lightness_min` / `lightness_max` | how pale or deep the colors can be |
| `adaptive.source`, `high` / `low`, `max_boost`, `lightness_push` | what to compare against (`wallpaper` or `theme`), the distance range, and how strong the boost is |
| `fade_in.updates_per_second` | update rate while a fade runs (match the screen refresh); nothing is sent otherwise |
| `fade_in.duration` / `native` | seconds for the grey-to-gradient fade, and whether Hyprland (`true`) or the daemon (`false`) does it |
| `bands.colors`, `highlights`, `wide` | colored stops, white glints, and how many bands may be doubled (keep colors + highlights at 10 or less) |
| `shimmer.enabled`, `seconds_per_band`, `updates_per_second`, `white_chance` | the band-to-band fade, its speed, its update rate, and the chance each step that a band fades to white instead |
| `sweep.enabled`, `on_switch`, `follow`, `bounce` / `back_speed` / `back`, `workspace`, `periodic`, `interval_min` / `interval_max`, `delay`, `duration`, `style` / `glow_tint`, `width`, `lines` / `line_gap` / `line_grey`, `rim` / `rim_width`, `distance`, `opacity_dark` / `opacity_bright`, `fade_in`, `sides` | the sweep: whether one runs on each switch, whether it moves away from the previous window, how far it drifts back at the end and how fast, whether it also runs a full pass back, the passes for a workspace switch, the delay before it starts, whether it also repeats, the range of seconds between sweeps, how long one runs, glow or hard bars and how much color the glow keeps, its width, how many lines it's made of, the gap between them and how grey the trailing ones are, the darker rim around it, how far it travels (fractions of the edge), its peak white opacity on a dark and a bright wallpaper, how much of the run it spends fading in, and whether it can run along the sides |
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

`gen-holo-border.py` builds the band colors (from the sticker palette or the theme's `colors.toml`, adjusted for
the wallpaper), writes the gradient where Hyprland loads it, and writes the patched border shader.
`drift.py` is a small daemon that listens for Hyprland's focus events. It sets the focused window's own border
color (`hl.dsp.window.set_prop`, far cheaper for Hyprland than changing the config): 10 updates a second for the
slow neighbor fade, and 60 a second for about a second after a switch for the fade-in and the sweep. When you
switch away, it parks the old window's border at grey so its next fade-in starts clean. If Hyprland reloads its
config (a theme or wallpaper change) it sends the border again. `holo off` stops the daemon and sets every
window's border back to Omarchy's.

Cost (measured on a 4K screen): about 1.5% of one CPU core for the daemon and 2-3% extra for Hyprland while the
border is on, and about 15 MB of memory. Turning the neighbor fade off (`shimmer.continuous = false`) brings the
idle cost to nearly nothing.

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

`lib/shaders/gradient.glsl.in` is derived from Hyprland's `gradient.glsl` and keeps Hyprland's BSD 3-Clause
license (copyright vaxerski); the notice is at the top of that file.
