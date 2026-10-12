#!/usr/bin/env python3
"""Drift, tilt and flash for the holo border.

Hyprland's built-in border loop can't go slower than ~10s per turn, so this
daemon turns the gradient angle itself over Hyprland's command socket:

- drift:  the angle moves at a speed that wanders smoothly, reversing direction
          every few seconds (easing through zero)
- tilt:   the cursor's position inside the focused window shifts the angle
- settle: after a few idle seconds the drift slows down
- flash:  selecting a window briefly shows the theme's complementary colors,
          which fade back to the normal ones

Colors come from colors.json (written by gen-holo-border.py) and are reloaded
whenever that file changes, e.g. after a theme switch.
"""
import json, os, random, socket, time

import holo_config

cfg = holo_config.load()
MIN_SPEED, MAX_SPEED = cfg["drift"]["min_speed"], cfg["drift"]["max_speed"]
RETARGET = (cfg["drift"]["leg_min"], cfg["drift"]["leg_max"])
EASE = cfg["drift"]["ease"]
HZ = cfg["drift"]["updates_per_second"]
TILT_X, TILT_Y, TILT_EASE = cfg["tilt"]["x"], cfg["tilt"]["y"], cfg["tilt"]["ease"]
SETTLE_AFTER, SETTLED_FACTOR = cfg["settle"]["after"], cfg["settle"]["factor"]
SETTLE_EASE, CURSOR_MOVED_PX = cfg["settle"]["ease"], cfg["settle"]["cursor_px"]
FLASH_HOLD, FLASH_FADE = cfg["flash"]["hold"], cfg["flash"]["fade"]
WINDOW_EVERY = 0.25   # seconds between active-window geometry lookups

COLORS = os.path.expanduser("~/.local/state/holo/colors.json")
SOCK = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket.sock"

def parse(c):
    h = c[5:13]
    return [int(h[i:i + 2], 16) for i in (0, 2, 4, 6)]

def load_colors():
    d = json.load(open(COLORS))
    return [parse(c) for c in d["normal"]], [parse(c) for c in d["complement"]]

def blend(normal, comp, t):
    """t=0 -> normal colors, t=1 -> complementary; returns rgba() strings."""
    return [
        "rgba(%02x%02x%02x%02x)" % tuple(round(a + (b - a) * t) for a, b in zip(n, c))
        for n, c in zip(normal, comp)
    ]

def send(cmd):
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(1)
    s.connect(SOCK)
    s.send(cmd.encode())
    data = b""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    return data.decode()

def cursor_offset(win, cur):
    """Cursor position inside the active window as (-1..1, -1..1); None if outside."""
    if not win:
        return None
    (x, y), (w, h) = win
    if w <= 0 or h <= 0:
        return None
    nx, ny = (cur["x"] - x) / w * 2 - 1, (cur["y"] - y) / h * 2 - 1
    if abs(nx) > 1 or abs(ny) > 1:
        return None
    return nx, ny

def main():
    (normal, comp), mtime = load_colors(), os.path.getmtime(COLORS)
    flash_at = -1e9
    angle = random.uniform(0, 360)
    direction = 1
    speed = target = (MIN_SPEED + MAX_SPEED) / 2
    retarget_at = 0.0
    tilt = 0.0
    factor = 1.0
    aw = {}
    last_focus, last_cursor, active_at = None, None, time.monotonic()
    win, win_at = None, 0.0
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
        angle = (angle + speed * factor * dt) % 360
        try:
            if now >= win_at:
                aw = json.loads(send("j/activewindow") or "{}")
                win = (aw["at"], aw["size"]) if aw.get("at") else None
                win_at = now + WINDOW_EVERY
            cur = json.loads(send("j/cursorpos"))
            focus = aw.get("address") if win else None
            if focus != last_focus and last_focus is not None and focus is not None:
                flash_at = now
            if focus != last_focus or (last_cursor and
                    abs(cur["x"] - last_cursor[0]) + abs(cur["y"] - last_cursor[1]) > CURSOR_MOVED_PX):
                active_at = now
            last_focus, last_cursor = focus, (cur["x"], cur["y"])
            goal_factor = SETTLED_FACTOR if now - active_at > SETTLE_AFTER else 1.0
            factor += (goal_factor - factor) * min(1.0, SETTLE_EASE * dt)
            off = cursor_offset(win, cur)
            goal = 0.0 if off is None else off[0] * TILT_X + off[1] * TILT_Y
            tilt += (goal - tilt) * min(1.0, TILT_EASE * dt)
            m = os.path.getmtime(COLORS)
            if m != mtime:
                (normal, comp), mtime = load_colors(), m
            if not normal:
                continue
            flash = max(0.0, min(1.0, 1 - (now - flash_at - FLASH_HOLD) / FLASH_FADE))
            cl = ",".join(f'"{c}"' for c in blend(normal, comp, flash))
            send(f"eval hl.config({{general={{col={{active_border={{colors={{{cl}}},angle={(angle + tilt) % 360:.1f}}}}}}}}})")
        except Exception:
            time.sleep(1)

if __name__ == "__main__":
    main()
