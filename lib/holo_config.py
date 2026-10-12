"""Shared settings loader: built-in defaults overridden by config.toml."""
import copy, os, tomllib

PATH = os.environ.get("HOLO_CONFIG") or os.path.expanduser("~/.config/hypr/holo/config.toml")

DEFAULTS = {
    "border": {"size": 3, "alpha": 0.85},
    "colors": {
        "lightness_min": 0.84, "lightness_max": 0.92,
        "chroma_min": 0.075, "chroma_max": 0.13,
        "grey_chroma": 0.012, "contrast": 2.109375,
    },
    "drift": {
        "min_speed": 4.5, "max_speed": 16.5,
        "leg_min": 1.0, "leg_max": 6.0,
        "ease": 2.5, "updates_per_second": 20,
    },
    "tilt": {"x": 55.0, "y": 30.0, "ease": 6.0},
    "settle": {"after": 3.0, "factor": 1 / 3, "ease": 0.8, "cursor_px": 6},
    "flash": {"hold": 0.6, "fade": 2.4},
    "adaptive": {"enabled": True, "source": "wallpaper", "high": 0.60, "low": 0.25, "max_boost": 0.4, "lightness_push": 0.15},
}

def load():
    cfg = copy.deepcopy(DEFAULTS)
    try:
        with open(PATH, "rb") as f:
            user = tomllib.load(f)
    except FileNotFoundError:
        return cfg
    for section, values in user.items():
        if section in cfg and isinstance(values, dict):
            cfg[section].update(values)
    return cfg
