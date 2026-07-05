"""
Trilateration engine for BLE Room Positioning System.
Converts RSSI readings from multiple anchors into 2D position estimates.
"""

import math
import numpy as np
from scipy.optimize import least_squares


def rssi_to_distance(rssi, tx_power=-59, path_loss_exponent=2.0):
    """
    Convert RSSI to estimated distance using the log-distance path loss model.

    Formula: distance = 10 ^ ((tx_power - rssi) / (10 * n))

    Args:
        rssi: Received Signal Strength Indicator (dBm, negative value)
        tx_power: Reference TX power at 1 meter distance (dBm)
        path_loss_exponent: Path loss exponent (2.0 = free space, 2.7-3.5 = indoor)

    Returns:
        Estimated distance in meters
    """
    if rssi == 0 or rssi >= 0:
        return float("inf")

    exponent = (tx_power - rssi) / (10.0 * path_loss_exponent)
    distance = math.pow(10, exponent)

    # Clamp to reasonable range (0.1m to 50m)
    return max(0.1, min(distance, 50.0))


def filter_outliers(distances, threshold_factor=2.0):
    """
    Filter outlier distance measurements using median absolute deviation.

    Args:
        distances: List of (anchor_id, distance) tuples
        threshold_factor: How many MADs from median to consider outlier

    Returns:
        Filtered list of (anchor_id, distance) tuples
    """
    if len(distances) <= 2:
        return distances

    dist_values = [d for _, d in distances]
    median = np.median(dist_values)
    mad = np.median([abs(d - median) for d in dist_values])

    if mad == 0:
        return distances

    filtered = [
        (aid, d)
        for aid, d in distances
        if abs(d - median) / (mad + 1e-10) < threshold_factor
    ]

    # Always keep at least 3 if possible
    if len(filtered) < 3 and len(distances) >= 3:
        return distances[:3]

    return filtered


def trilaterate(anchor_distances, anchor_positions):
    """
    Estimate 2D position using least-squares trilateration.

    Given distances from known anchor positions, find the point (x, y) that
    best fits all distance constraints.

    Args:
        anchor_distances: List of (anchor_id, distance_meters) tuples
        anchor_positions: Dict of anchor_id -> (x, y) in meters

    Returns:
        dict with keys:
            - position: (x, y) tuple in meters, or None if failed
            - error: estimated position error in meters
            - anchors_used: number of anchors used in calculation
            - method: algorithm used
    """
    # Build arrays of anchor positions and distances
    valid = []
    for anchor_id, distance in anchor_distances:
        if anchor_id in anchor_positions and distance > 0 and distance < float("inf"):
            ax, ay = anchor_positions[anchor_id]
            valid.append((ax, ay, distance))

    if len(valid) < 3:
        return {
            "position": None,
            "error": None,
            "anchors_used": len(valid),
            "method": "insufficient_data",
            "message": f"Need at least 3 anchors, got {len(valid)}",
        }

    anchors = np.array([[v[0], v[1]] for v in valid])
    distances = np.array([v[2] for v in valid])

    # Objective function: sum of squared residuals
    # For each anchor: (distance_from_point_to_anchor - measured_distance)^2
    def residuals(point):
        x, y = point
        result = []
        for i in range(len(anchors)):
            ax, ay = anchors[i]
            measured_dist = distances[i]
            calculated_dist = math.sqrt((x - ax) ** 2 + (y - ay) ** 2)
            result.append(calculated_dist - measured_dist)
        return result

    # Initial guess: centroid of anchor positions
    x0 = np.mean(anchors[:, 0])
    y0 = np.mean(anchors[:, 1])
    initial_guess = np.array([x0, y0])

    try:
        # Run least-squares optimization
        result = least_squares(
            residuals,
            initial_guess,
            method="lm",  # Levenberg-Marquardt
            max_nfev=1000,
        )

        estimated_x, estimated_y = result.x

        # Calculate position error (RMS of residuals)
        res = residuals(result.x)
        error = math.sqrt(sum(r ** 2 for r in res) / len(res))

        return {
            "position": (round(estimated_x, 2), round(estimated_y, 2)),
            "error": round(error, 3),
            "anchors_used": len(valid),
            "method": "least_squares",
        }

    except Exception as e:
        return {
            "position": None,
            "error": None,
            "anchors_used": len(valid),
            "method": "failed",
            "message": str(e),
        }


def calculate_position(beacon_id, scan_data_by_anchor, anchor_positions, calibration):
    """
    Full pipeline: take raw scan data from multiple anchors and calculate beacon position.

    Args:
        beacon_id: The beacon MAC address to locate
        scan_data_by_anchor: Dict of anchor_id -> list of beacon readings
            Each reading: {"beacon_id": "...", "rssi": -65, "tx_power": -59}
        anchor_positions: Dict of anchor_id -> (x, y)
        calibration: Dict with path_loss_exponent, tx_power_dbm, min_rssi_threshold

    Returns:
        dict with position, error, details per anchor
    """
    path_loss_exp = calibration.get("path_loss_exponent", 2.0)
    default_tx = calibration.get("tx_power_dbm", -59)
    min_rssi = calibration.get("min_rssi_threshold", -90)

    anchor_distances = []
    anchor_details = []

    for anchor_id, beacons in scan_data_by_anchor.items():
        # Find the target beacon in this anchor's scan
        target = None
        for b in beacons:
            if b["beacon_id"] == beacon_id:
                target = b
                break

        if target is None:
            continue

        rssi = target["rssi"]

        # Filter weak signals
        if rssi < min_rssi:
            continue

        # Use beacon-specific TX power if available, else default
        tx_power = target.get("tx_power", default_tx)
        if not isinstance(tx_power, (int, float)) or not -100 <= tx_power <= -20:
            tx_power = default_tx

        # Convert RSSI to distance
        distance = rssi_to_distance(rssi, tx_power, path_loss_exp)

        anchor_distances.append((anchor_id, distance))
        anchor_details.append({
            "anchor_id": anchor_id,
            "rssi": rssi,
            "tx_power": tx_power,
            "estimated_distance_m": round(distance, 2),
        })

    # Filter outliers
    filtered_distances = filter_outliers(anchor_distances)

    # Run trilateration
    result = trilaterate(filtered_distances, anchor_positions)

    # Add beacon info and anchor details
    result["beacon_id"] = beacon_id
    result["anchor_details"] = anchor_details

    return result
