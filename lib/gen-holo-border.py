#!/usr/bin/env python3
"""Generate the holo border colors from the current Omarchy theme.

Writes ~/.config/hypr/holo-border.lua (loaded by Hyprland) and
~/.local/state/holo/colors.json (read by drift.py: the normal colors plus a
complementary set for the flash when you select a window).

Dark themes: pastel, brightened, contrast-boosted tints of the theme's blue,
cyan, magenta, yellow and bright_blue, alternating with white/silver glints,
then clamped into a fixed OKLCH lightness/chroma band so every theme has the
same contrast. Light themes use the theme colors as-is with grey glints.
"""
import colorsys, json, math, os, re, subprocess, tomllib

import holo_config

cfg = holo_config.load()
theme = os.environ.get("HOLO_THEME") or os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml")
colors_json = os.environ.get("HOLO_JSON") or os.path.expanduser("~/.local/state/holo/colors.json")
out = os.environ.get("HOLO_OUT") or os.path.expanduser("~/.config/hypr/holo-border.lua")
WALLPAPER = os.path.realpath(os.environ.get("HOLO_WALLPAPER") or os.path.expanduser("~/.local/state/omarchy/current/background"))

ALPHA = cfg["border"]["alpha"]
BORDER_SIZE = cfg["border"]["size"]
SH = cfg["shadow"]
FADE_IN = cfg["fade_in"]["duration"]
NATIVE_FADE = cfg["fade_in"]["native"]
CONTRAST = cfg["colors"]["contrast"]
L_MIN, L_MAX = cfg["colors"]["lightness_min"], cfg["colors"]["lightness_max"]
C_MIN, C_MAX = cfg["colors"]["chroma_min"], cfg["colors"]["chroma_max"]
GREY_CHROMA = cfg["colors"]["grey_chroma"]
RAW = cfg["colors"]["raw"]
AD = cfg["adaptive"]

with open(theme, "rb") as f:
    c = tomllib.load(f)

light = c.get("mode") == "light"
accent = c.get("accent", "#dcd7ba")
get = lambda k: c.get(k, accent)

def to_lin(v):
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def from_lin(v):
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055

def rgb_to_oklch(v):
    r, g, b = [to_lin(x) for x in v]
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360

def oklch_to_rgb(L, C, H):
    """OKLCH -> sRGB 0-255, reducing chroma until the color is in gamut."""
    while True:
        a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
        l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
               -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
               -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
        if all(-0.002 <= x <= 1.002 for x in rgb) or C <= 0:
            return [max(0, min(255, round(from_lin(max(0.0, min(1.0, x))) * 255))) for x in rgb]
        C -= 0.004

def limit(v):
    L, C, H = rgb_to_oklch(v)
    C = GREY_CHROMA if C < 0.03 else max(C_MIN, min(C_MAX, C))
    return oklch_to_rgb(max(L_MIN, min(L_MAX, L)), C, H)

def rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]

def style(h):
    v = rgb(h)
    if light or RAW:
        return v
    v = [x + (255 - x) * 0.40 for x in v]          # pastel
    v = [x * 1.25 for x in v]                       # brighter
    return limit([max(0, min(255, round(273 + (x - 273) * CONTRAST))) for x in v])

def dominant_color():
    """Most common color of the wallpaper (falls back to the theme background)."""
    if AD["source"] == "wallpaper":
        wall = WALLPAPER
        try:
            text = subprocess.run(
                ["magick", wall, "-resize", "96x96!", "-colors", "8", "-depth", "8",
                 "-format", "%c", "histogram:info:-"],
                capture_output=True, text=True, timeout=10).stdout
            found = [(int(m.group(1)), [int(m.group(i)) for i in (2, 3, 4)])
                     for m in re.finditer(r"(\d+):\s*\(\s*(\d+),\s*(\d+),\s*(\d+)", text)]
            if found:
                return max(found)[1]
        except (OSError, subprocess.SubprocessError):
            pass
    return rgb(c.get("background", "#000000"))

def lab(v):
    L, C, H = rgb_to_oklch(v)
    return L, C * math.cos(math.radians(H)), C * math.sin(math.radians(H))

def hexa(v):
    return "rgba(%02x%02x%02x%02x)" % (*v, round(ALPHA * 255))

dominant = dominant_color()
dom_lab = lab(dominant)

TR = cfg["transparency"]

def wallpaper_pixels():
    """A 32x32 sample of the wallpaper as [r, g, b] rows; the theme background if unavailable."""
    if AD["source"] == "wallpaper":
        wall = WALLPAPER
        try:
            text = subprocess.run(["magick", wall, "-resize", "32x32!", "-depth", "8", "txt:-"],
                                  capture_output=True, text=True, timeout=10).stdout
            px = [[int(x) for x in m.groups()] for m in re.finditer(r"\((\d+),(\d+),(\d+)", text)]
            if px:
                return px
        except (OSError, subprocess.SubprocessError):
            pass
    return [rgb(c.get("background", "#000000"))]

WALL = wallpaper_pixels()
WALL_L = sum(rgb_to_oklch(p)[0] for p in WALL) / len(WALL)

def wallpaper_brightness():
    """Brightness score 0..1: mean OKLCH lightness of the wallpaper, scaled between
    TR dark_l (score 0) and TR bright_l (score 1)."""
    return max(0.0, min(1.0, (WALL_L - TR["dark_l"]) / (TR["bright_l"] - TR["dark_l"])))

BRIGHTNESS = wallpaper_brightness()
if TR["enabled"]:
    # Brighter backdrop -> more opaque border so the pale colors don't wash out; above solid_above
    # the border is fully opaque.
    ALPHA = min(1.0, TR["min_alpha"] + (TR["max_alpha"] - TR["min_alpha"]) * BRIGHTNESS)
    if BRIGHTNESS > TR["solid_above"]:
        ALPHA = 1.0

def adapt(v):
    """Boost one color by how close it is to the dominant color behind the border.

    Far from it (>= high): untouched. Close (<= low): more chroma, and lightness
    pushed away from the dominant color's lightness.
    """
    if not AD["enabled"] or RAW:
        return v
    dist = math.dist(lab(v), dom_lab)
    m = max(0.0, min(1.0, (AD["high"] - dist) / (AD["high"] - AD["low"])))
    if m == 0.0:
        return v
    L, C, H = rgb_to_oklch(v)
    if C >= 0.03:                       # near-greys stay neutral
        C *= 1 + AD["max_boost"] * m
    L += (-1 if dom_lab[0] > 0.5 else 1) * AD["lightness_push"] * m
    return oklch_to_rgb(max(0.0, min(1.0, L)), C, H)

base_colors = [style(get(k)) for k in ("blue", "cyan", "magenta", "yellow", "bright_blue")]

white = [255, 255, 255] if not light else [150, 156, 166]
silver = [251, 255, 255] if not light else [120, 126, 138]

blue, cyan, magenta, yellow, bright_blue = [adapt(v) for v in base_colors]

LG = cfg["legibility"]

def luminance(v):
    return 0.2126 * to_lin(v[0]) + 0.7152 * to_lin(v[1]) + 0.0722 * to_lin(v[2])

def contrast_score(colors):
    """Mean WCAG contrast ratio (1 = none, 21 = black on white) between the border colors,
    drawn at the current opacity, and the wallpaper pixels behind them."""
    total = 0.0
    for v in colors:
        for p in WALL:
            top = luminance([x * ALPHA + y * (1 - ALPHA) for x, y in zip(v, p)])
            bot = luminance(p)
            total += (max(top, bot) + 0.05) / (min(top, bot) + 0.05)
    return total / (len(colors) * len(WALL))

def legible(colors):
    """Move the colored stops' lightness until their mean contrast with the wallpaper reaches the
    target. Both directions are tried and the one that gets there with the smaller move wins
    (or, if neither does, the one that gets closest); a move that doesn't improve contrast is
    never taken. Lightness stays within [min_lightness, max_lightness], so the colors never sink
    to near-black or wash out to white; on a bright wallpaper the outline makes up the rest."""
    if not LG["enabled"]:
        return colors
    target = LG["target_dark"] + (LG["target_bright"] - LG["target_dark"]) * BRIGHTNESS
    lch = [rgb_to_oklch(v) for v in colors]
    lo, hi = (0.0 if light else LG["min_lightness"]), LG["max_lightness"]   # light themes keep their deep colors

    def shifted(shift):
        # darker stops at lo (or where the color already was, if below it); lighter stops at hi
        new = lambda L: max(L + shift, min(L, lo)) if shift < 0 else min(L + shift, max(L, hi))
        return [oklch_to_rgb(new(L), C, H) for L, C, H in lch]

    best, best_score, best_shift = colors, contrast_score(colors), 0.0
    if best_score >= target:
        return colors
    for step in (0.02, -0.02):
        shift = 0.0
        while abs(shift) < LG["max_shift"] - 1e-9:
            shift += step
            out = shifted(shift)
            score = contrast_score(out)
            reached, best_reached = score >= target, best_score >= target
            if (reached and (not best_reached or abs(shift) < abs(best_shift))) or (not best_reached and score > best_score + 1e-3):
                best, best_score, best_shift = out, score, shift
            if reached:
                break
    return best

COLOR_NAMES = ("blue", "cyan", "magenta", "yellow", "bright_blue")
contrast_target = LG["target_dark"] + (LG["target_bright"] - LG["target_dark"]) * BRIGHTNESS
contrast_before = contrast_score([blue, cyan, magenta, yellow, bright_blue])
blue, cyan, magenta, yellow, bright_blue = legible([blue, cyan, magenta, yellow, bright_blue])

def vivid_up(colors):
    """More chroma on bright wallpapers (none on dark ones), so the darker colors the contrast
    step needs still look rich instead of muddy. Stays inside the sRGB gamut."""
    boost = 1 + cfg["vividness"]["max_boost"] * BRIGHTNESS if cfg["vividness"]["enabled"] else 1
    out = []
    for v in colors:
        L, C, H = rgb_to_oklch(v)
        out.append(oklch_to_rgb(L, C * boost, H))
    return out

blue, cyan, magenta, yellow, bright_blue = vivid_up([blue, cyan, magenta, yellow, bright_blue])
final = dict(zip(COLOR_NAMES, [blue, cyan, magenta, yellow, bright_blue]))   # what is drawn; opposites derive from these
contrast_after = contrast_score([blue, cyan, magenta, yellow, bright_blue])
stops = [
    (white, "white"), (blue, "blue"), (white, "white"),
    (cyan, "cyan"), (white, "white"), (silver, "silver"),
    (magenta, "magenta"), (white, "white"),
    (yellow, "yellow"), (white, "white"), (silver, "silver"),
    (bright_blue, "bright_blue"), (white, "white"),
]

def complement(v):
    """The color directly across the color wheel (hue + 180 degrees), made vivid: the opposite
    only reads as an opposite if it is bright and saturated, whatever the original's lightness."""
    h, s, val = colorsys.rgb_to_hsv(*[x / 255 for x in v])
    r, g, b = colorsys.hsv_to_rgb((h + 0.5) % 1.0, max(s, 0.85), max(val, 0.95))
    return [round(r * 255), round(g * 255), round(b * 255)]

RING_SAMPLES = 48   # the hue ring is written this finely so drift.py can interpolate it linearly

def hue_ring(colors):
    """The colors around the color wheel in hue order, closed into a loop, with a bridge color
    (OKLCH midpoint) between each pair of hue neighbors, then sampled evenly in OKLab so every
    color fades smoothly into the next, like the bands on holo foil."""
    lch = [rgb_to_oklch(v) for v in colors]
    chromatic = sorted((p for p in lch if p[1] >= 0.03), key=lambda p: p[2])
    keep = []
    for p in chromatic:                       # drop near-duplicates (e.g. blue and bright_blue)
        if not keep or math.dist(lab(oklch_to_rgb(*p)), lab(oklch_to_rgb(*keep[-1]))) > 0.04:
            keep.append(p)
    if len(keep) < 2:
        keep = sorted(lch, key=lambda p: p[2])
    knots = []
    for i, (L, C, H) in enumerate(keep):
        L2, C2, H2 = keep[(i + 1) % len(keep)]
        gap = (H2 - H) % 360 or 360
        knots += [(L, C, H), ((L + L2) / 2, (C + C2) / 2, (H + gap / 2) % 360)]
    labs = [lab(oklch_to_rgb(*k)) for k in knots]
    ring = []
    for s in range(RING_SAMPLES):
        pos = s / RING_SAMPLES * len(labs)
        a, b, f = labs[int(pos)], labs[(int(pos) + 1) % len(labs)], pos % 1
        L, A, B = [x + (y - x) * f for x, y in zip(a, b)]
        ring.append(oklch_to_rgb(L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360))
    return ring

ring = hue_ring(list(final.values()))
OL = cfg["outline"]
# Sticker edge: a dark keyline, stronger on a bright wallpaper where the pale colors need it most.
outline = [12, 10, 18, round(255 * (OL["min_alpha"] + (OL["max_alpha"] - OL["min_alpha"]) * BRIGHTNESS))]

os.makedirs(os.path.dirname(colors_json), exist_ok=True)

# Border shader override: loops the 10 colors bands.repeat times (loaded by "holo" with hyprctl reloadshaders).
shader_out = os.path.join(os.path.dirname(colors_json), "shaders", "gradient.glsl")
# The sweep's starting opacity follows the wallpaper brightness score, like the border opacity:
# white shows up easily over a dark wallpaper's bands and needs more on a bright one.
SW = cfg["sweep"]
SWEEP_OPACITY = SW["opacity_dark"] + (SW["opacity_bright"] - SW["opacity_dark"]) * BRIGHTNESS
if cfg["bands"]["repeat"] > 1:
    os.makedirs(os.path.dirname(shader_out), exist_ok=True)
    template = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shaders", "gradient.glsl.in")).read()
    for key, val in (("@REPEAT@", str(int(cfg["bands"]["repeat"]))),
                     ("@BAR_WIDTH@", "%.4f" % cfg["sweep"]["width"]), ("@SWEEP_DIST@", "%.4f" % cfg["sweep"]["distance"]),
                     ("@SWEEP_OPACITY@", "%.4f" % SWEEP_OPACITY)):
        template = template.replace(key, val)
    open(shader_out, "w").write(template)
elif os.path.exists(shader_out):
    os.remove(shader_out)
with open(colors_json, "w") as f:
    json.dump({
        "normal": [hexa(v) for v, n in stops],
        "complement": [hexa(v if n in ("white", "silver") else complement(final[n])) for v, n in stops],
        "brightness": round(BRIGHTNESS, 3), "alpha": round(ALPHA, 3), "sweep_opacity": round(SWEEP_OPACITY, 3),
        "names": [n for v, n in stops],
        "ring": [hexa(v) for v in ring], "ring_complement": [hexa(complement(v)) for v in ring],
        "highlight": hexa(white), "outline": "rgba(%02x%02x%02x%02x)" % tuple(outline),
        "contrast_before": round(contrast_before, 2), "contrast_target": round(contrast_target, 2), "contrast": round(contrast_after, 2),
    }, f)

lines = "\n".join('      "%s", -- %s' % (hexa(v), n) for v, n in stops)
open(out, "w").write(f'''-- GENERATED by holo-border (gen-holo-border.py) from the current theme. Do not edit.
hl.config({{
  decoration = {{
    shadow = {{
      enabled = {str(SH["enabled"] or OL["enabled"]).lower()},
      range = {OL["range"] if OL["enabled"] else SH["range"]},
      render_power = {OL["render_power"] if OL["enabled"] else SH["render_power"]},
      color_inactive = "rgba(00000000)", -- focused window only; drift.py sets the active color
      color = "rgba(00000000)",
    }},
  }},
  general = {{
    border_size = {BORDER_SIZE},
    col = {{
      active_border = {{
        colors = {{
{lines}
        }},
        angle = {cfg["border"]["angle"]},
      }},
    }},
  }},
}})

-- The angle is driven by drift.py, so Hyprland's built-in border loop is off.
hl.animation({{ leaf = "borderangle", enabled = false }})
{"-- Hyprland fades inactive grey -> holo itself on focus change (fade_in.native)." if NATIVE_FADE else "-- No color animation on focus change (drift.py fades grey -> holo itself)."}
hl.animation({{ leaf = "border", enabled = {str(NATIVE_FADE).lower()}, speed = {FADE_IN * 10:g}, bezier = "linear" }})
''')
