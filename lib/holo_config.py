"""Shared settings loader: built-in defaults overridden by config.toml."""
import copy, os, tomllib

PATH = os.environ.get("HOLO_CONFIG") or os.path.expanduser("~/.config/hypr/holo/config.toml")

DEFAULTS = {
    "border": {"size": 3, "alpha": 0.6},
    "colors": {
        "lightness_min": 0.84, "lightness_max": 0.92,
        "chroma_min": 0.075, "chroma_max": 0.13,
        "grey_chroma": 0.012, "raw": False, "contrast": 2.109375,
    },
    "drift": {
        "min_speed": 2.25, "max_speed": 8.25,
        "leg_min": 1.0, "leg_max": 6.0,
        "ease": 2.5, "updates_per_second": 60,
    },
    "settle": {"after": 3.0, "factor": 1 / 3, "ease": 0.8},
    "opposites": {"stops": [5, 10], "fade": 5.0},
    "shadow": {"enabled": True, "range": 5, "render_power": 3, "alpha": 0.1},
    "fade_in": {"duration": 0.25},
    "sweep": {"degrees": 45.0, "duration": 3.6, "clockwise_sign": -1},
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
