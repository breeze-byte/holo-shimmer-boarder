#!/usr/bin/env python3
"""Drift, fade, opposites and shadow for the holo border.

Hyprland's built-in border loop can't go slower than ~10s per turn, so this
daemon turns the gradient angle itself over Hyprland's command socket:

- drift:  the angle moves at a speed that wanders smoothly, reversing direction
          every few seconds (easing through zero)
- settle: after a few idle seconds the drift slows down
- bands:  7 stops (white, then 3 random theme colors with a silver between each, white), re-randomized on every window switch
- opposites: the silvers start as the opposite of the color before them, fading to silver
- shadow: a faint shadow tinted from the gradient fades in with the border and stays
- fade:   selecting a window fades the border from the inactive grey to the holo colors
"""
import json, os, random, socket, subprocess, sys, threading, time

import holo_config

cfg = holo_config.load()
MIN_SPEED, MAX_SPEED = cfg["drift"]["min_speed"], cfg["drift"]["max_speed"]
RETARGET = (cfg["drift"]["leg_min"], cfg["drift"]["leg_max"])
EASE = cfg["drift"]["ease"]
HZ = cfg["drift"]["updates_per_second"]
SETTLE_AFTER, SETTLED_FACTOR, SETTLE_EASE = cfg["settle"]["after"], cfg["settle"]["factor"], cfg["settle"]["ease"]
FADE_IN = cfg["fade_in"]["duration"]
INACTIVE = (0x59, 0x59, 0x59, 0xaa)   # Hyprland's inactive border (aa595959)
SHADOW_ON, SHADOW_ALPHA = cfg["shadow"]["enabled"], cfg["shadow"]["alpha"]
OPP_FADE = cfg["opposites"]["fade"]
BAND_COLORS = cfg["bands"]["colors"]

SOCK = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket.sock"
COLORS = os.path.expanduser("~/.local/state/holo/colors.json")   # written by gen-holo-border.py
WALLPAPER = os.path.expanduser("~/.local/state/omarchy/current/background")
GENERATOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen-holo-border.py")
WALLPAPER_EVERY = 3.0   # seconds between wallpaper-change checks
focus_at = -1e9
state = {"colors": None, "angle": 0.0}   # latest border, shared with the event thread   # when focus last changed (set by the event thread)

def ease(x):
    """Smootherstep: 0 -> 1 with zero speed and acceleration at both ends."""
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)

def load_colors():
    """(normal, complement, names): stop lists as [r, g, b, a] rows, and each stop's name."""
    d = json.load(open(COLORS))
    parse = lambda cs: [[int(c[5:13][i:i + 2], 16) for i in (0, 2, 4, 6)] for c in cs]
    return parse(d["normal"]), parse(d["complement"]), d["names"]

def new_layout(names):
    """Pick BAND_COLORS theme colors in a random order: white, color, silver, color, ..., white.
    Each entry is (source stop, stop whose opposite it starts as or None)."""
    colored = [i for i, n in enumerate(names) if n not in ("white", "silver")]
    pick = random.sample(colored, min(BAND_COLORS, len(colored)))
    white, silver = names.index("white"), names.index("silver")
    layout = [(white, None)]
    for n, c in enumerate(pick):
        layout.append((c, None))
        layout.append((silver, c) if n < len(pick) - 1 else (white, None))
    return layout

def with_opposites(layout, normal, comp, since_focus):
    """Silver stops start as the opposite of the color before them, then fade back."""
    k = ease(since_focus / OPP_FADE)
    return [[round(a + (b - a) * k) for a, b in zip(comp[opp], normal[src])] if opp is not None else list(normal[src])
            for src, opp in layout]

def shadow_color(colors, angle, t):
    """Shadow tint = the gradient's color at this angle (skipping the white stops), faded in by t."""
    tint = [c for c in colors if min(c[:3]) < 250] or colors
    pos = (angle % 360) / 360 * len(tint)
    a, b, f = tint[int(pos) % len(tint)], tint[(int(pos) + 1) % len(tint)], pos % 1
    rgb = [round(x + (y - x) * f) for x, y in zip(a[:3], b[:3])]
    return "rgba(%02x%02x%02x%02x)" % (*rgb, round(255 * SHADOW_ALPHA * t))

def eval_colors(colors, t, angle, shadow_t=None):
    """Border at fade position t (0 = inactive grey, 1 = holo colors) and the given angle;
    the shadow fades in with it (shadow_t overrides its position)."""
    sh = ""
    if SHADOW_ON:
        sh = ',decoration={shadow={color="%s"}}' % shadow_color(colors, angle, t if shadow_t is None else shadow_t)
    cl = ",".join('"rgba(%02x%02x%02x%02x)"' % tuple(round(g + (v - g) * t) for g, v in zip(INACTIVE, c)) for c in colors)
    return "eval hl.config({general={col={active_border={colors={%s},angle=%.1f}}}%s})" % (cl, angle % 360, sh)

def wallpaper_stamp():
    try:
        real = os.path.realpath(WALLPAPER)
        return real, os.path.getmtime(real)
    except OSError:
        return None

def send(cmd):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(1)
    s.connect(SOCK)
    s.send(cmd.encode())
    while s.recv(65536):
        pass
    s.close()

def watch_focus():
    global focus_at
    path = SOCK.replace(".socket.sock", ".socket2.sock")
    while True:
        try:
            s = socket.socket(socket.AF_UNIX)
            s.connect(path)
            buf, last = b"", None
            while chunk := s.recv(4096):
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for l in lines:
                    # Hyprland repeats this event on every title change (e.g. a terminal
                    # spinner), so only a different window address counts as a switch.
                    if l.startswith(b"activewindowv2>>") and l != last:
                        last, focus_at = l, time.monotonic()
                        # Hyprland has already painted the new window in full holo; drop to
                        # grey right away so the fade starts from grey, not from a flash.
                        if state["colors"]:
                            send(eval_colors(state["colors"], 0.0, state["angle"], 0.0))
        except Exception:
            time.sleep(1)

def main():
    threading.Thread(target=watch_focus, daemon=True).start()
    (normal, comp, names), mtime = load_colors(), os.path.getmtime(COLORS)
    layout, layout_for = new_layout(names), focus_at
    wall, wall_at = wallpaper_stamp(), 0.0
    angle = random.uniform(0, 360)
    direction = 1
    speed = target = (MIN_SPEED + MAX_SPEED) / 2
    retarget_at = 0.0
    factor = 1.0
    last = next_tick = time.monotonic()
    while True:
        # Fixed schedule (not sleep(1/HZ)) so frame timing doesn't drift.
        next_tick += 1 / HZ
        time.sleep(max(0.0, next_tick - time.monotonic()))
        now = time.monotonic()
        dt, last = now - last, now
        if now >= retarget_at:
            direction = -direction
            target = direction * random.uniform(MIN_SPEED, MAX_SPEED)
            retarget_at = now + random.uniform(*RETARGET)
        speed += (target - speed) * min(1.0, EASE * dt)
        goal_factor = SETTLED_FACTOR if now - focus_at > SETTLE_AFTER else 1.0
        factor += (goal_factor - factor) * min(1.0, SETTLE_EASE * dt)
        angle = (angle + speed * factor * dt) % 360
        try:
            if cfg["adaptive"]["enabled"] and cfg["adaptive"]["source"] == "wallpaper" and now >= wall_at:
                wall_at = now + WALLPAPER_EVERY
                stamp = wallpaper_stamp()
                if stamp != wall:                  # new wallpaper: re-sample its dominant color
                    wall = stamp
                    subprocess.run([sys.executable, GENERATOR], timeout=30)
            m = os.path.getmtime(COLORS)
            if m != mtime:
                (normal, comp, names), mtime = load_colors(), m
                layout = new_layout(names)
            if layout_for != focus_at:        # new window: a fresh random arrangement (hidden by the fade-in)
                layout, layout_for = new_layout(names), focus_at
            colors = with_opposites(layout, normal, comp, now - focus_at)
            state["colors"], state["angle"] = colors, angle
            send(eval_colors(colors, ease((now - focus_at) / FADE_IN), angle))
        except Exception:
            time.sleep(1)

if __name__ == "__main__":
    main()
