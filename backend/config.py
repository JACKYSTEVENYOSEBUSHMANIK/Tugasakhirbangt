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
