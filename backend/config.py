"""
Configuration for the BLE Room Positioning System.
Stores room dimensions, anchor positions, and calibration parameters.
"""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "room": {
        "width_m": 10.0,   # Room width in meters
        "height_m": 8.0,   # Room height in meters
    },
    "anchors": {
        "scanner-01": {
            "x": 0.0,
            "y": 0.0,
            "label": "Anchor 1 (Bottom-Left)",
        },
        "scanner-02": {
            "x": 10.0,
            "y": 0.0,
            "label": "Anchor 2 (Bottom-Right)",
        },
        "scanner-03": {
            "x": 5.0,
            "y": 8.0,
            "label": "Anchor 3 (Top-Center)",
        },
    },
    "calibration": {
        "path_loss_exponent": 2.0,   # Free-space path loss exponent (tune: 2.0-4.0)
        "tx_power_dbm": -59,         # Reference TX power at 1 meter (tune per beacon)
        "min_rssi_threshold": -90,    # Ignore signals weaker than this
        "scan_ttl_seconds": 15,      # How long scan data is considered fresh
        "heatmap_stationary_radius_m": 0.5,  # Max movement between samples to count as "dwelling"
        "heatmap_max_gap_seconds": 300,      # Max gap between samples before treating as offline
    },
    "zones": {
        "Ruang VIP": {"x_min": 0.0, "x_max": 5.0, "y_min": 0.0, "y_max": 4.0},
        "Pantry": {"x_min": 5.0, "x_max": 10.0, "y_min": 0.0, "y_max": 4.0},
        "Lobi": {"x_min": 0.0, "x_max": 10.0, "y_min": 4.0, "y_max": 8.0}
    },
    "beacon_filters": [],  # List of beacon MAC addresses to track (empty = track all)
}

def load_config():
    """Load configuration from JSON file, or create default."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    # Create default config file
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_anchor_positions(config=None):
    """Return dict of anchor_id -> (x, y) tuples."""
    if config is None:
        config = load_config()
    positions = {}
    for anchor_id, data in config.get("anchors", {}).items():
        positions[anchor_id] = (data["x"], data["y"])
    return positions


def get_calibration_params(config=None):
    """Return calibration parameters."""
    if config is None:
        config = load_config()
    return config.get("calibration", DEFAULT_CONFIG["calibration"])


def update_anchor_position(anchor_id, x, y, config=None):
    """Update a single anchor's position."""
    if config is None:
        config = load_config()
    if anchor_id in config["anchors"]:
        config["anchors"][anchor_id]["x"] = x
        config["anchors"][anchor_id]["y"] = y
        save_config(config)
        return True
    return False


def update_calibration_params(params, config=None):
    """Update calibration parameters."""
    if config is None:
        config = load_config()
    config["calibration"].update(params)
    save_config(config)


def update_room_dimensions(width_m, height_m, config=None):
    """Update the overall room's dimensions."""
    if config is None:
        config = load_config()
    config["room"]["width_m"] = round(float(width_m), 1)
    config["room"]["height_m"] = round(float(height_m), 1)
    save_config(config)
    return config["room"]


def list_zones(config=None):
    """Return zones as a list of {name, x_min, x_max, y_min, y_max}."""
    if config is None:
        config = load_config()
    zones = config.get("zones", {})
    return [{"name": name, **bbox} for name, bbox in zones.items()]


def add_or_update_zone(name, x_min, x_max, y_min, y_max, config=None):
    """Create a new zone or overwrite an existing one by name."""
    if config is None:
        config = load_config()
    name = name.strip()
    if not name:
        raise ValueError("Zone name is required")
    x_min, x_max = round(float(x_min), 1), round(float(x_max), 1)
    y_min, y_max = round(float(y_min), 1), round(float(y_max), 1)
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min
    config.setdefault("zones", {})[name] = {
        "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
    }
    save_config(config)
    return {"name": name, "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max}


def delete_zone(name, config=None):
    """Remove a zone by name. Returns True if it existed."""
    if config is None:
        config = load_config()
    zones = config.get("zones", {})
    if name in zones:
        del zones[name]
        save_config(config)
        return True
    return False
