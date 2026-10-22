"""Shared settings loader: built-in defaults overridden by config.toml."""
import copy, os, tomllib

PATH = os.environ.get("HOLO_CONFIG") or os.path.expanduser("~/.config/hypr/holo/config.toml")

DEFAULTS = {
    "border": {"size": 3, "alpha": 0.6, "angle": 315},
    "colors": {
        "lightness_min": 0.84, "lightness_max": 0.92,
        "chroma_min": 0.075, "chroma_max": 0.13,
        "grey_chroma": 0.012, "raw": False, "contrast": 2.109375,
    },
    "opposites": {"fade": 1.5},
    "bands": {"colors": 10, "highlights": 0, "wide": 0, "repeat": 3},
    "shimmer": {"enabled": True, "seconds_per_band": 1.5, "direction": -1, "updates_per_second": 30},
    "outline": {"enabled": True, "range": 2, "render_power": 4, "min_alpha": 0.25, "max_alpha": 0.85},
    "transparency": {"enabled": True, "min_alpha": 0.38, "max_alpha": 1.0, "dark_l": 0.2, "bright_l": 0.8},
    "legibility": {"enabled": True, "target_dark": 2.0, "target_bright": 4.0, "max_shift": 0.45},
    "vividness": {"enabled": True, "max_boost": 0.8},
    "shadow": {"enabled": True, "range": 5, "render_power": 3, "alpha": 0.03},
    "fade_in": {"duration": 0.3, "native": False, "updates_per_second": 60},
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
