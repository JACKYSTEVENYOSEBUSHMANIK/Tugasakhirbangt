"""
Flask REST API for BLE Room Positioning System.
Receives BLE scan data from ESP32 anchors, performs trilateration,
and serves position data to the React frontend.
"""

import time
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime

import database
from config import (
    load_config,
    save_config,
    get_anchor_positions,
    get_calibration_params,
    update_anchor_position,
    update_calibration_params,
)
from trilateration import calculate_position, rssi_to_distance

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================
# In-memory data store
# ============================================================
# scan_store: {anchor_id: {"timestamp": ..., "beacons": [...], "anchor_pos": [x,y]}}
scan_store = {}
scan_store_lock = threading.Lock()

# position_cache: {beacon_id: {position, error, ...}}
position_cache = {}
position_cache_lock = threading.Lock()

# Event log buffer (circular, keeps last 200 entries)
MAX_LOGS = 200
event_logs = []
event_logs_lock = threading.Lock()


def add_log(level, source, message, data=None):
    """Add a log entry and emit it via WebSocket."""
    entry = {
        "timestamp": time.time() * 1000,
        "time_str": time.strftime("%H:%M:%S"),
        "level": level,       # INFO, WARN, ERROR, SCAN, HTTP
        "source": source,     # ESP, BACKEND, TRILAT, SYSTEM
        "message": message,
        "data": data,
    }
    with event_logs_lock:
        event_logs.append(entry)
        if len(event_logs) > MAX_LOGS:
            event_logs.pop(0)
    # Emit to all connected WebSocket clients
    socketio.emit("log", entry)


def is_scan_fresh(anchor_id, ttl_seconds=15):
    """Check if scan data for an anchor is still fresh."""
    if anchor_id not in scan_store:
        return False
    entry = scan_store[anchor_id]
    # Use server time for freshness check
    return (time.time() * 1000 - entry.get("received_at", 0)) < ttl_seconds * 1000


def run_trilateration_for_all_beacons():
    """Run trilateration for all beacons visible to 3+ anchors."""
    config = load_config()
    anchor_positions = get_anchor_positions(config)
    calibration = get_calibration_params(config)
    beacon_filters = config.get("beacon_filters", [])
    ttl = calibration.get("scan_ttl_seconds", 15)

    # Collect beacons seen across all fresh scans
    beacon_readings = {}  # beacon_id -> {anchor_id -> [beacon_data]}

    with scan_store_lock:
        for anchor_id, scan_entry in scan_store.items():
            # Skip stale data
            if (time.time() * 1000 - scan_entry.get("received_at", 0)) > ttl * 1000:
                continue

            for beacon in scan_entry.get("beacons", []):
                bid = beacon["beacon_id"]

                # Apply beacon filter if configured
                if beacon_filters and bid not in beacon_filters:
                    continue

                if bid not in beacon_readings:
                    beacon_readings[bid] = {}

                beacon_readings[bid][anchor_id] = beacon

    # Count active (fresh) anchors
    active_anchor_count = 0
    with scan_store_lock:
        for anchor_id, scan_entry in scan_store.items():
            if (time.time() * 1000 - scan_entry.get("received_at", 0)) < ttl * 1000:
                active_anchor_count += 1

    # Calculate position for each beacon
    results = {}
    for beacon_id, anchor_beacon_map in beacon_readings.items():
        if len(anchor_beacon_map) < 3:
            continue  # Require at least 3 anchors for trilateration

        # Format scan_data_by_anchor for calculate_position
        scan_data_by_anchor = {}
        for anchor_id, beacon_data in anchor_beacon_map.items():
            scan_data_by_anchor[anchor_id] = [beacon_data]

        result = calculate_position(
            beacon_id, scan_data_by_anchor, anchor_positions, calibration
        )

        results[beacon_id] = result

    # Update position cache
    with position_cache_lock:
        position_cache.clear()
        position_cache.update(results)

    # Emit real-time position update via WebSocket
    socketio.emit("positions_update", {
        "positions": list(results.values()),
        "timestamp": time.time() * 1000,
        "active_anchors": active_anchor_count,
        "system_ready": active_anchor_count >= 3,
    })

    # Save positions to NeonDB in background
    if results:
        def db_save_positions_async(positions):
            for bid, res in positions.items():
                if res.get("position"):
                    pos = res["position"]
                    database.save_beacon_position(
                        bid,
                        pos[0],
                        pos[1],
                        res.get("error", 0.0),
                        res.get("anchors_used", 0),
                        datetime.utcnow()
                    )
        threading.Thread(
            target=db_save_positions_async,
            args=(results,),
            daemon=True
        ).start()

    return results


# ============================================================
# REST API Endpoints
# ============================================================

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    config = load_config()
    calibration = get_calibration_params(config)
    ttl = calibration.get("scan_ttl_seconds", 15)

    # Count anchors with fresh data
    active_anchors = 0
    with scan_store_lock:
        for anchor_id, entry in scan_store.items():
            if (time.time() * 1000 - entry.get("received_at", 0)) < ttl * 1000:
                active_anchors += 1

    total_anchors = len(config.get("anchors", {}))

    return jsonify({
        "status": "ok",
        "uptime_seconds": time.time(),
        "anchors_reporting": active_anchors,
        "anchors_total": total_anchors,
        "beacons_tracked": len(position_cache),
        "system_ready": active_anchors >= 3,
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Get recent event logs."""
    limit = request.args.get("limit", 100, type=int)
    with event_logs_lock:
        logs = event_logs[-limit:]
    return jsonify({
        "logs": logs,
        "count": len(logs),
    })


@app.route("/api/scan", methods=["POST"])
def receive_scan():
    """
    Receive BLE scan data from an ESP32 anchor.

    Expected JSON:
    {
        "anchor_id": "scanner-02",
        "anchor_pos": [2.5, 3.0],
        "timestamp": 1709945025000,
        "calibration_mode": false,
        "beacons": [
            {"beacon_id": "AA:BB:CC:DD:EE:FF", "rssi": -65, "tx_power": -59}
        ]
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    anchor_id = data.get("anchor_id")
    if not anchor_id:
        return jsonify({"error": "anchor_id is required"}), 400

    # Store scan data with server receive time
    beacons = data.get("beacons", [])
    with scan_store_lock:
        scan_store[anchor_id] = {
            "anchor_id": anchor_id,
            "anchor_pos": data.get("anchor_pos"),
            "timestamp": data.get("timestamp"),
            "received_at": time.time() * 1000,
            "calibration_mode": data.get("calibration_mode", False),
            "beacons": beacons,
        }

    # Log the incoming scan
    beacon_summary = []
    for b in beacons:
        beacon_summary.append(f"{b.get('beacon_id', '?')[-8:]}@{b.get('rssi', '?')}dBm")
    beacon_str = ", ".join(beacon_summary) if beacon_summary else "none"
    add_log("SCAN", "ESP", f"{anchor_id} reported {len(beacons)} beacon(s): {beacon_str}", {
        "anchor_id": anchor_id,
        "beacon_count": len(beacons),
        "beacons": beacons,
        "timestamp": data.get("timestamp"),
        "calibration_mode": data.get("calibration_mode", False),
    })

    # Log each beacon individually for detailed view
    for b in beacons:
        bid = b.get("beacon_id", "?")
        rssi = b.get("rssi", "?")
        tx = b.get("tx_power", "?")
        name = b.get("name", "")
        name_str = f" ({name})" if name else ""
        add_log("INFO", "ESP", f"  {anchor_id} -> {bid}{name_str} | RSSI: {rssi} dBm | TX: {tx} dBm")

    # Save scan data to NeonDB in background
    if beacons:
        def db_save_scan_async(aid, anchor_pos, b_list):
            x = anchor_pos[0] if anchor_pos and len(anchor_pos) > 0 else 0.0
            y = anchor_pos[1] if anchor_pos and len(anchor_pos) > 1 else 0.0
            database.save_anchor(aid, x, y, aid)
            
            config_data = load_config()
            calib = get_calibration_params(config_data)
            path_loss_exp = calib.get("path_loss_exponent", 2.0)
            default_tx = calib.get("tx_power_dbm", -59)
            
            for b in b_list:
                bid = b.get("beacon_id")
                rssi = b.get("rssi")
                tx = b.get("tx_power", default_tx)
                if not isinstance(tx, (int, float)) or not -100 <= tx <= -20:
                    tx = default_tx
                name = b.get("name", "Unknown")
                
                database.save_beacon(bid, name)
                distance = rssi_to_distance(rssi, tx, path_loss_exp)
                database.save_rssi_log(aid, bid, rssi, tx, distance, datetime.utcnow())

        threading.Thread(
            target=db_save_scan_async,
            args=(anchor_id, data.get("anchor_pos"), beacons),
            daemon=True
        ).start()

    # Run trilateration in background
    try:
        results = run_trilateration_for_all_beacons()
        if len(results) > 0:
            for bid, res in results.items():
                if res.get("position"):
                    pos = res["position"]
                    add_log("INFO", "TRILAT", f"{bid[-8:]} positioned at ({pos[0]}, {pos[1]}) | err: {res.get('error', '?')}m | anchors: {res.get('anchors_used', '?')}")
                else:
                    add_log("WARN", "TRILAT", f"{bid[-8:]} position failed: {res.get('message', 'unknown')}")
        else:
            active = sum(1 for e in scan_store.values() if (time.time() * 1000 - e.get("received_at", 0)) < 15000)
            if active < 3 and active > 0:
                add_log("WARN", "TRILAT", f"Only {active}/3 anchors reporting - need 3 for trilateration")
    except Exception as e:
        add_log("ERROR", "TRILAT", f"Trilateration error: {e}")
        results = {}

    return jsonify({
        "status": "received",
        "anchor_id": anchor_id,
        "beacons_count": len(beacons),
        "positions_calculated": len(results),
    }), 200


@app.route("/api/positions", methods=["GET"])
def get_positions():
    """Get current beacon positions (trilateration results)."""
    with position_cache_lock:
        positions = list(position_cache.values())

    return jsonify({
        "positions": positions,
        "count": len(positions),
        "timestamp": time.time() * 1000,
    })


@app.route("/api/anchors", methods=["GET"])
def get_anchors():
    """Get anchor configurations and status."""
    config = load_config()
    anchors_data = config.get("anchors", {})
    calibration = get_calibration_params(config)
    ttl = calibration.get("scan_ttl_seconds", 15)

    result = []
    for anchor_id, info in anchors_data.items():
        # Check if anchor is online (has recent scan data)
        online = False
        last_seen = None
        beacon_count = 0

        with scan_store_lock:
            if anchor_id in scan_store:
                entry = scan_store[anchor_id]
                last_seen = entry.get("received_at")
                online = (time.time() * 1000 - (last_seen or 0)) < ttl * 1000
                beacon_count = len(entry.get("beacons", []))

        result.append({
            "anchor_id": anchor_id,
            "x": info["x"],
            "y": info["y"],
            "label": info.get("label", anchor_id),
            "online": online,
            "last_seen": last_seen,
            "beacons_detected": beacon_count,
        })

    return jsonify({
        "anchors": result,
        "count": len(result),
    })


@app.route("/api/anchors", methods=["PUT"])
def update_anchors():
    """
    Update anchor positions (calibration).

    Expected JSON:
    {
        "anchors": [
            {"anchor_id": "scanner-01", "x": 0.0, "y": 0.0},
            {"anchor_id": "scanner-02", "x": 10.0, "y": 0.0}
        ]
    }
    """
    data = request.get_json()
    if not data or "anchors" not in data:
        return jsonify({"error": "anchors array is required"}), 400

    updated = []
    for anchor in data["anchors"]:
        aid = anchor.get("anchor_id")
        x = anchor.get("x")
        y = anchor.get("y")
        if aid and x is not None and y is not None:
            if update_anchor_position(aid, float(x), float(y)):
                updated.append(aid)

    return jsonify({
        "status": "updated",
        "updated_anchors": updated,
    })


@app.route("/api/history/positions", methods=["GET"])
def get_positions_history():
    """Get historical position estimates for a beacon."""
    beacon_id = request.args.get("beacon_id")
    if not beacon_id:
        return jsonify({"error": "beacon_id parameter is required"}), 400
    limit = request.args.get("limit", 100, type=int)
    history = database.get_beacon_positions_history(beacon_id, limit)
    return jsonify({
        "beacon_id": beacon_id,
        "history": history,
        "count": len(history)
    })


@app.route("/api/history/rssi", methods=["GET"])
def get_rssi_history():
    """Get historical RSSI scanner readings for a beacon."""
    beacon_id = request.args.get("beacon_id")
    if not beacon_id:
        return jsonify({"error": "beacon_id parameter is required"}), 400
    limit = request.args.get("limit", 100, type=int)
    history = database.get_rssi_history(beacon_id, limit)
    return jsonify({
        "beacon_id": beacon_id,
        "history": history,
        "count": len(history)
    })


@app.route("/api/scan-data", methods=["GET"])
def get_scan_data():
    """Get latest raw RSSI scan data from all anchors."""
    calibration = get_calibration_params()
    ttl = calibration.get("scan_ttl_seconds", 15)
    result = []

    with scan_store_lock:
        for anchor_id, entry in scan_store.items():
            age_ms = time.time() * 1000 - entry.get("received_at", 0)
            if age_ms < ttl * 1000:
                result.append({
                    "anchor_id": entry["anchor_id"],
                    "anchor_pos": entry.get("anchor_pos"),
                    "timestamp": entry.get("timestamp"),
                    "calibration_mode": entry.get("calibration_mode", False),
                    "beacons": entry.get("beacons", []),
                    "age_seconds": round(age_ms / 1000, 1),
                })

    return jsonify({
        "scan_data": result,
        "active_anchors": len(result),
    })


@app.route("/api/calibrate", methods=["POST"])
def calibrate():
    """
    Update calibration parameters.

    Expected JSON (any subset):
    {
        "path_loss_exponent": 2.5,
        "tx_power_dbm": -59,
        "min_rssi_threshold": -90,
        "scan_ttl_seconds": 15
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No calibration data provided"}), 400

    allowed_keys = {
        "path_loss_exponent", "tx_power_dbm",
        "min_rssi_threshold", "scan_ttl_seconds",
    }

    params = {k: v for k, v in data.items() if k in allowed_keys}
    if not params:
        return jsonify({"error": "No valid calibration parameters"}), 400

    update_calibration_params(params)

    # Re-run trilateration with new params
    try:
        results = run_trilateration_for_all_beacons()
    except Exception:
        results = {}

    return jsonify({
        "status": "calibrated",
        "params": params,
        "positions_recalculated": len(results),
    })


@app.route("/api/calibrate", methods=["GET"])
def get_calibration():
    """Get current calibration parameters."""
    config = load_config()
    return jsonify({
        "calibration": get_calibration_params(config),
        "room": config.get("room", {}),
        "beacon_filters": config.get("beacon_filters", []),
    })


@app.route("/api/config", methods=["GET"])
def get_full_config():
    """Get full system configuration."""
    return jsonify(load_config())


@app.route("/api/config", methods=["PUT"])
def update_config():
    """Update full system configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No config data provided"}), 400
    save_config(data)
    return jsonify({"status": "config_updated"})


# ============================================================
# WebSocket events
# ============================================================

@socketio.on("connect")
def handle_connect():
    """Client connected - send current positions and logs."""
    with position_cache_lock:
        positions = list(position_cache.values())

    emit("positions_update", {
        "positions": positions,
        "timestamp": time.time() * 1000,
    })

    # Send existing logs to the new client
    with event_logs_lock:
        logs = list(event_logs[-50:])
    emit("logs_init", {"logs": logs})


@socketio.on("request_positions")
def handle_request_positions():
    """Client requests fresh positions."""
    try:
        results = run_trilateration_for_all_beacons()
        emit("positions_update", {
            "positions": list(results.values()),
            "timestamp": time.time() * 1000,
        })
    except Exception as e:
        emit("error", {"message": str(e)})


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("BLE Room Positioning System - Backend")
    print("=" * 50)

    config = load_config()
    print(f"Room: {config['room']['width_m']}m x {config['room']['height_m']}m")
    print(f"Anchors: {len(config['anchors'])}")
    for aid, ainfo in config["anchors"].items():
        print(f"  {aid}: ({ainfo['x']}, {ainfo['y']})")
    print(f"Calibration: n={config['calibration']['path_loss_exponent']}, "
          f"tx={config['calibration']['tx_power_dbm']} dBm")
    print("=" * 50)

    # Add startup logs (will be emitted once socketio starts)
    import threading
    def log_startup():
        time.sleep(1)  # Wait for socketio to be ready
        add_log("INFO", "SYSTEM", "Backend server started on port 5000")
        add_log("INFO", "SYSTEM", f"Room: {config['room']['width_m']}m x {config['room']['height_m']}m")
        add_log("INFO", "SYSTEM", f"Waiting for ESP32 anchors to connect...")
        add_log("INFO", "SYSTEM", "POST /api/scan to send BLE scan data")
    threading.Thread(target=log_startup, daemon=True).start()

    # Keep a single stable process so server.ps1 can manage its PID reliably.
    # The debug reloader spawns a child process and can break WebSocket requests.
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
