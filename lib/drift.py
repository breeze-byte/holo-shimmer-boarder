#!/usr/bin/env python3
"""Fade, bands, opposites and shadow for the holo border.

The gradient itself is static (no drift), so while nothing is happening this
daemon sends Hyprland nothing at all. On a window switch it works over
Hyprland's command socket for a fraction of a second:

- bands:  colored stops taken in order around a hue ring of the theme colors (so each band flows
          into the next), with a few white glints and some doubled (wider) bands; the start,
          direction, glints and wide bands are re-randomized on every window switch
- shimmer: on a window switch each band fades into its neighbor's color once, then holds
          (shimmer.continuous keeps it flowing instead)
- opposites: the glints start as the opposite of the color before them, fading to white
- shadow: a dark sticker-edge outline (or a faint tint from the gradient) fades in with the border
- fade:   selecting a window fades the border from the inactive grey to the holo colors
- sweep:  after a switch's fade-in, then every 5-30 s (random), a white bar runs along the focused window's border,
          across the top and bottom or along the sides, in a random direction
          (drawn by the holo shader; the daemon only sends their position in a control stop)
"""
import json, os, random, socket, subprocess, sys, threading, time

import holo_config

cfg = holo_config.load()
HZ = cfg["fade_in"]["updates_per_second"]
ANGLE = cfg["border"]["angle"]
FADE_IN = cfg["fade_in"]["duration"]
NATIVE_FADE = cfg["fade_in"]["native"]   # Hyprland does the grey -> holo fade; we only keep the colors current
INACTIVE = (0x59, 0x59, 0x59, 0xaa)   # Hyprland's inactive border (aa595959)
SHADOW_ON, SHADOW_ALPHA = cfg["shadow"]["enabled"], cfg["shadow"]["alpha"]
OPP_FADE = cfg["opposites"]["fade"]
BANDS = cfg["bands"]
MAX_STOPS = 10   # Hyprland accepts more gradient colors but only draws the first 10
SWEEP = cfg["sweep"]
SHADER = os.path.expanduser("~/.local/state/holo/shaders/gradient.glsl")   # written by gen-holo-border.py
# The sweep needs the holo shader (it reads the 10th stop as the bar position, not a color).
SWEEP_ON = SWEEP["enabled"] and os.path.exists(SHADER) and "holoBar" in open(SHADER).read()
COLOR_STOPS = MAX_STOPS - 1 if SWEEP_ON else MAX_STOPS
N_GLINTS = max(0, min(BANDS["highlights"], COLOR_STOPS - 2))
N_COLORS = max(2, min(BANDS["colors"], COLOR_STOPS - N_GLINTS))
SHIMMER = cfg["shimmer"]
OUTLINE_ON = cfg["outline"]["enabled"]

SOCK = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket.sock"
COLORS = os.path.expanduser("~/.local/state/holo/colors.json")   # written by gen-holo-border.py
WALLPAPER = os.path.expanduser("~/.local/state/omarchy/current/background")
GENERATOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen-holo-border.py")
WALLPAPER_EVERY = 3.0   # seconds between wallpaper-change checks
SHADOW_EVERY = 5.0      # seconds between shadow-tint updates while the colors drift
focus_at = -1e9   # when focus last changed (set by the event thread)
send_lock = threading.Lock()    # border commands go out one at a time, in the order they were decided
focus_evt = threading.Event()   # wakes the main loop the moment focus changes
sent_at = 0.0                   # when we last sent a border command
resend = threading.Event()      # Hyprland reloaded its config and reset the border: send it again
state = {"colors": None, "angle": float(ANGLE), "outline": "rgba(00000000)", "sweep": [0, 0, 0, 0],
         "addr": None}   # the focused window's address ("0x..."), set by the event thread   # latest border, shared with the event thread

def ease(x):
    """Smootherstep: 0 -> 1 with zero speed and acceleration at both ends."""
    x = max(0.0, min(1.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)

def load_colors():
    """The palette from colors.json: the hue ring and its complements as [r, g, b, a] rows,
    the white glint color, and the outline color."""
    d = json.load(open(COLORS))
    parse = lambda c: [int(c[5:13][i:i + 2], 16) for i in (0, 2, 4, 6)]
    return {"ring": [parse(c) for c in d["ring"]], "comp": [parse(c) for c in d["ring_complement"]],
            "white": parse(d["highlight"]), "outline": d["outline"]}

def new_layout(ring_len):
    """A fresh random arrangement: a list of ("ring", offset) colored stops and ("glint", offset)
    white glints, where offset is a position on the hue ring (in ring samples). The colored stops
    step along the ring in hue order from a random start, spanning it once; a few steps are 0
    (a doubled, wider band); glints sit between colored stops and remember their neighbor."""
    n = N_COLORS
    step = ring_len / n
    wide = set(random.sample(range(1, n), min(BANDS["wide"], (n - 1) // 3)))   # most bands stay distinct
    pos, offsets = random.uniform(0, ring_len), []
    for i in range(n):
        if i and i not in wide:
            pos += step
        offsets.append(pos)
    layout = [("ring", p) for p in offsets]
    for g in sorted(random.sample(range(1, n), min(N_GLINTS, n - 1)), reverse=True):
        layout.insert(g, ("glint", offsets[g - 1]))
    return layout

def sample(ring, pos):
    """The ring's color at a fractional position, wrapping around."""
    i, f = int(pos // 1), pos % 1
    a, b = ring[i % len(ring)], ring[(i + 1) % len(ring)]
    return [round(x + (y - x) * f) for x, y in zip(a, b)]

def stop_colors(layout, pal, since_focus, now):
    """Each stop's color now: colored stops slide along the ring (the shimmer), always in the
    same direction; glints start as the opposite of the color before them and fade to white."""
    ring_len = len(pal["ring"])
    shift = 0.0
    if SHIMMER["enabled"]:   # direction 1: each band takes the color of the one after it, so the pattern flows toward the gradient's start
        # continuous: keep flowing; otherwise each band fades into its neighbor once per window switch, then holds
        bands = now / SHIMMER["seconds_per_band"] if SHIMMER["continuous"] else ease(since_focus / SHIMMER["seconds_per_band"])
        shift = SHIMMER["direction"] * bands * ring_len / N_COLORS
    k = ease(since_focus / OPP_FADE)
    out = []
    for kind, pos in layout:
        if kind == "ring":
            out.append(sample(pal["ring"], pos + shift))
        else:
            out.append([round(a + (b - a) * k) for a, b in zip(sample(pal["comp"], pos + shift), pal["white"])])
    return out

def next_sweep(after, now):
    """A new random sweep: (start time, mode). It starts interval_min..interval_max seconds after
    the previous one started (after), but not before now; mode bit 0 runs it along the sides (else
    the top and bottom), bit 1 runs it backward (right to left, or down)."""
    return max(now, after + random.uniform(SWEEP["interval_min"], SWEEP["interval_max"])), random.randrange(4)

def sweep_stop(sweep, now):
    """The control stop for the holo shader: black, with the sweep in its alpha: 0 = none, else
    1 + mode * 63 + step (step 0..62 = start..end, at a steady pace)."""
    start, mode = sweep
    x = (now - start) / SWEEP["duration"]
    if not 0.0 <= x < 1.0:
        return [0, 0, 0, 0]
    return [0, 0, 0, 1 + mode * 63 + round(x * 62)]

def shadow_color(colors, angle, t):
    """Outline color, or a tint = the gradient's color at this angle (skipping the white stops), faded in by t."""
    if OUTLINE_ON:
        o = state["outline"]
        return "%s%02x)" % (o[:-3], round(int(o[-3:-1], 16) * t))   # rgba(rrggbbAA): scale the AA
    tint = [c for c in colors if min(c[:3]) < 250] or colors
    pos = (angle % 360) / 360 * len(tint)
    a, b, f = tint[int(pos) % len(tint)], tint[(int(pos) + 1) % len(tint)], pos % 1
    rgb = [round(x + (y - x) * f) for x, y in zip(a[:3], b[:3])]
    return "rgba(%02x%02x%02x%02x)" % (*rgb, round(255 * SHADOW_ALPHA * t))

def border_cmd(colors, t, angle):
    """Border of the focused window at fade position t (0 = inactive grey, 1 = holo colors) and the
    given angle, set as that window's own active_border_color. Much cheaper for Hyprland than
    changing the config (hl.config re-applies the whole config: ~6x the CPU per update)."""
    if not state["addr"]:
        return None
    cl = " ".join("rgba(%02x%02x%02x%02x)" % tuple(round(g + (v - g) * t) for g, v in zip(INACTIVE, c)) for c in colors)
    if SWEEP_ON:
        cl += " rgba(%02x%02x%02x%02x)" % tuple(state["sweep"])
    return ('dispatch hl.dsp.window.set_prop({ prop = "active_border_color", value = "%s %ddeg", window = "address:%s" })'
            % (cl, round(angle) % 360, state["addr"]))

def shadow_cmd(colors, angle, t):
    """The focused-window shadow color (it's global config, so it's sent sparingly), or None."""
    if not (SHADOW_ON or OUTLINE_ON):
        return None
    return 'eval hl.config({decoration={shadow={color="%s"}}})' % shadow_color(colors, angle, t)

def wallpaper_stamp():
    try:
        real = os.path.realpath(WALLPAPER)
        return real, os.path.getmtime(real)
    except OSError:
        return None

def query(cmd):
    """Send a command over Hyprland's command socket and return its reply."""
    s = socket.socket(socket.AF_UNIX)
    s.settimeout(1)
    s.connect(SOCK)
    s.send(cmd.encode())
    reply = b""
    while chunk := s.recv(65536):
        reply += chunk
    s.close()
    return reply.decode()

def send(cmd):
    global sent_at
    sent_at = time.monotonic()
    query(cmd)

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
                    # A reload (theme or wallpaper change, holo refresh) resets the border to the static
                    # holo-border.lua gradient: always re-send. Our own eval commands don't emit this
                    # event (checked on 0.56), so this can't loop, and ignoring reloads that land right
                    # after a send of ours would leave the fallback gradient up.
                    if l.startswith(b"configreloaded"):
                        resend.set()
                        focus_evt.set()
                    # Hyprland repeats this event on every title change (e.g. a terminal
                    # spinner), so only a different window address counts as a switch.
                    if l.startswith(b"activewindowv2>>") and l != last:
                        last = l
                        with send_lock:
                            focus_at = time.monotonic()
                            state["addr"] = ("0x" + l[16:].decode().strip()) if l[16:].strip() else None
                            # Hyprland has already painted the new window in full holo; drop to
                            # grey right away so the fade starts from grey, not from a flash.
                            if state["colors"] and not NATIVE_FADE and state["addr"]:
                                send(border_cmd(state["colors"], 0.0, state["angle"]))
                        focus_evt.set()
        except Exception:
            time.sleep(1)

def main():
    threading.Thread(target=watch_focus, daemon=True).start()
    pal, mtime = load_colors(), os.path.getmtime(COLORS)
    state["outline"] = pal["outline"]
    layout, layout_for = new_layout(len(pal["ring"])), focus_at
    wall, wall_at = wallpaper_stamp(), 0.0
    angle = float(ANGLE)
    last_cmd = last_shadow = None
    shadow_at = 0.0
    try:   # the window focused at startup (later ones come from the event thread)
        state["addr"] = json.loads(query("j/activewindow")).get("address") or None
    except (OSError, ValueError):
        pass
    next_tick = time.monotonic()
    sweep = next_sweep(next_tick, next_tick)
    while True:
        # 60 updates a second while a window switch is still fading, the shimmer rate after that;
        # with the shimmer off, sleep until the next focus event (waking now and then to check
        # for a new wallpaper or theme).
        # A random sweep also runs at 60 a second, and the loop wakes up in time to start it.
        t = time.monotonic()
        busy = t - focus_at < max(FADE_IN, OPP_FADE, SHIMMER["seconds_per_band"]) + 0.1
        busy = busy or (SWEEP_ON and sweep[0] - 0.05 <= t < sweep[0] + SWEEP["duration"] + 0.1)
        flowing = SHIMMER["enabled"] and SHIMMER["continuous"]
        next_tick += 1 / HZ if busy else 1 / SHIMMER["updates_per_second"] if flowing else 1.0
        if SWEEP_ON and t < sweep[0] - 0.05:
            next_tick = min(next_tick, sweep[0] - 0.05)
        if focus_evt.wait(max(0.0, next_tick - time.monotonic())):   # woken early by a focus change
            focus_evt.clear()
            next_tick = time.monotonic()
        if resend.is_set() or time.monotonic() - sent_at > 30:   # a reload resets the border; also refresh now and then
            resend.clear()
            last_cmd = last_shadow = None
        now = time.monotonic()
        try:
            if cfg["adaptive"]["enabled"] and cfg["adaptive"]["source"] == "wallpaper" and now >= wall_at:
                wall_at = now + WALLPAPER_EVERY
                stamp = wallpaper_stamp()
                if stamp != wall:                  # new wallpaper: re-sample its dominant color
                    wall = stamp
                    subprocess.run([sys.executable, GENERATOR], timeout=30)
            m = os.path.getmtime(COLORS)
            if m != mtime:
                pal, mtime = load_colors(), m
                state["outline"] = pal["outline"]
                layout = new_layout(len(pal["ring"]))
            with send_lock:    # read focus_at and send in one step, so a stale update can't land after the grey drop
                since = time.monotonic() - focus_at
                if layout_for != focus_at:        # new window: a fresh random arrangement (hidden by the fade-in)
                    layout, layout_for = new_layout(len(pal["ring"])), focus_at
                    if SWEEP["on_switch"]:        # and a sweep once the fade-in is done (Hyprland's own fade ignores updates)
                        sweep = (focus_at + FADE_IN + 0.05, random.randrange(4))
                colors = stop_colors(layout, pal, since, time.monotonic())
                now = time.monotonic()
                if now >= sweep[0] + SWEEP["duration"]:   # this sweep is over: schedule the next one
                    sweep = next_sweep(sweep[0], now)
                state["colors"], state["angle"], state["sweep"] = colors, angle, sweep_stop(sweep, now)
                t_fade = 1.0 if NATIVE_FADE else ease(since / FADE_IN)
                cmd = border_cmd(colors, t_fade, angle)
                if cmd and cmd != last_cmd:       # nothing visibly changed: don't make Hyprland redo the border
                    send(cmd)
                    last_cmd = cmd
                # The shadow is global config, so only update it while a switch fades in, after a
                # reload, or every SHADOW_EVERY seconds as the colors drift.
                sh = shadow_cmd(colors, angle, t_fade)
                if sh and sh != last_shadow and (since < FADE_IN + 0.1 or last_shadow is None or now - shadow_at > SHADOW_EVERY):
                    send(sh)
                    last_shadow, shadow_at = sh, now
        except Exception:
            time.sleep(1)

if __name__ == "__main__":
    main()
