"""
Flask REST API for BLE Room Positioning System.
Receives BLE scan data from ESP32 anchors, performs trilateration,
and serves position data to the React frontend.
"""

import time
import threading
import math
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime

import database
import scheduler
import signal_monitor
from config import (
    load_config,
    save_config,
    get_anchor_positions,
    get_calibration_params,
    update_anchor_position,
    update_calibration_params,
    get_ruangan_for_position,
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


def check_and_update_tasks(positions_dict):
    """F5: Task Location Matching Check"""
    try:
        # Fetch all tasks from DB
        tasks = database.get_tasks()
        active_tasks = [t for t in tasks if t["status_tugas"] in ["Pending", "On Progress"]]
        if not active_tasks:
            return
            
        config_data = load_config()
        now = datetime.utcnow()
        
        for task in active_tasks:
            officer = task.get("petugas", {})
            beacon_id = officer.get("beacon_id")
            if not beacon_id or beacon_id not in positions_dict:
                continue
                
            pos_res = positions_dict[beacon_id]
            pos = pos_res.get("position")
            if not pos:
                continue
                
            current_ruangan = get_ruangan_for_position(pos[0], pos[1], config_data)
            target = task["target_ruangan"]
            status = task["status_tugas"]
            id_tugas = task["id_tugas"]
            
            if status == "Pending":
                if current_ruangan == target:
                    # Officer entered target room
                    database.update_task_status(id_tugas, "On Progress", waktu_mulai=now)
                    add_log("INFO", "SYSTEM", f"Tugas '{task['nama_tugas']}' dimulai (petugas memasuki {target})")
            elif status == "On Progress":
                # Check how long they've been in the room
                start_time_str = task.get("waktu_mulai")
                if start_time_str:
                    try:
                        # Parse ISO timestamp
                        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
                        duration = (now - start_time).total_seconds()
                        if current_ruangan == target:
                            if duration >= 10: # Minimum 10 seconds check-in
                                database.update_task_status(id_tugas, "Completed", waktu_selesai=now)
                                add_log("INFO", "SYSTEM", f"Tugas '{task['nama_tugas']}' selesai (petugas berada di {target} selama {int(duration)} detik)")
                        else:
                            # Completed because they checked it and left
                            database.update_task_status(id_tugas, "Completed", waktu_selesai=now)
                            add_log("INFO", "SYSTEM", f"Tugas '{task['nama_tugas']}' selesai (petugas telah memeriksa {target})")
                    except Exception as e:
                        print(f"Error calculating task duration: {e}")
    except Exception as ex:
        print(f"Error checking and updating tasks: {ex}")


def run_trilateration_for_all_beacons():
    """Run trilateration for all beacons visible to 3+ anchors."""
    config = load_config()
    anchor_positions = get_anchor_positions(config)
    calibration = get_calibration_params(config)
    beacon_filters = config.get("beacon_filters", [])
    ttl = calibration.get("scan_ttl_seconds", 15)
    
    # F1: Load per-anchor calibration parameters from database
    anchor_calibrations = {}
    try:
        anchors_db = database.get_anchors_list()
        for a in anchors_db:
            anchor_calibrations[a["anchor_id"]] = {
                "p_tx": a.get("p_tx", -59.0),
                "faktor_n": a.get("faktor_n", 2.0)
            }
    except Exception as e:
        print(f"Error loading per-anchor calibrations: {e}")

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

                # F4: Smart Tracking Toggle (Skip if officer not on shift)
                try:
                    if not database.is_petugas_on_shift(bid):
                        continue
                except Exception as e:
                    print(f"Error checking shift: {e}")

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
            beacon_id, scan_data_by_anchor, anchor_positions, calibration, anchor_calibrations
        )

        results[beacon_id] = result
        
        # F2: Update Signal Loss / Interference monitor
        try:
            with scan_store_lock:
                for aid, scan_entry in scan_store.items():
                    has_b = any(b["beacon_id"] == beacon_id for b in scan_entry.get("beacons", []))
                    if has_b:
                        signal_monitor.update_monitor_data(beacon_id, result, scan_entry)
                        break
        except Exception as e:
            print(f"Error updating signal monitor: {e}")

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

    # Save positions to NeonDB in background and run F5 task check
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
            # F5: Task Location Matching Check
            check_and_update_tasks(positions)
            
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
                
                # F4: Smart Tracking Toggle (skip if officer not on shift)
                try:
                    if not database.is_petugas_on_shift(bid):
                        continue
                except Exception as e:
                    print(f"Error checking shift: {e}")

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


# --- Shift Kerja API ---
@app.route("/api/shifts", methods=["GET", "POST", "PUT"])
def manage_shifts():
    if request.method == "GET":
        return jsonify({"shifts": database.get_shifts()})
    
    data = request.get_json() or {}
    nama_shift = data.get("nama_shift")
    jam_mulai = data.get("jam_mulai")
    jam_selesai = data.get("jam_selesai")
    
    if not all([nama_shift, jam_mulai, jam_selesai]):
        return jsonify({"error": "nama_shift, jam_mulai, and jam_selesai are required"}), 400
        
    id_shift = data.get("id_shift") if request.method == "PUT" else None
    
    success = database.save_shift(nama_shift, jam_mulai, jam_selesai, id_shift)
    if success:
        return jsonify({"status": "success", "message": "Shift saved successfully"})
    return jsonify({"error": "Failed to save shift"}), 500

@app.route("/api/shifts/<int:id_shift>", methods=["DELETE"])
def remove_shift(id_shift):
    success = database.delete_shift(id_shift)
    if success:
        return jsonify({"status": "success", "message": "Shift deleted successfully"})
    return jsonify({"error": "Failed to delete shift"}), 500


# --- Petugas API ---
@app.route("/api/petugas", methods=["GET", "POST", "PUT"])
def manage_petugas():
    if request.method == "GET":
        return jsonify({"petugas": database.get_petugas_list()})
        
    data = request.get_json() or {}
    nama = data.get("nama")
    beacon_id = data.get("beacon_id")
    id_shift = data.get("id_shift")
    
    if not nama:
        return jsonify({"error": "nama is required"}), 400
        
    id_petugas = data.get("id_petugas") if request.method == "PUT" else None
    
    success = database.save_petugas(nama, beacon_id, id_shift, id_petugas)
    if success:
        return jsonify({"status": "success", "message": "Petugas saved successfully"})
    return jsonify({"error": "Failed to save petugas"}), 500

@app.route("/api/petugas/<int:id_petugas>", methods=["DELETE"])
def remove_petugas(id_petugas):
    success = database.delete_petugas(id_petugas)
    if success:
        return jsonify({"status": "success", "message": "Petugas deleted successfully"})
    return jsonify({"error": "Failed to delete petugas"}), 500


# --- Tugas Petugas API ---
@app.route("/api/tasks", methods=["GET", "POST", "PUT"])
def manage_tasks():
    if request.method == "GET":
        limit = request.args.get("limit", 100, type=int)
        return jsonify({"tasks": database.get_tasks(limit)})
        
    data = request.get_json() or {}
    id_petugas = data.get("id_petugas")
    nama_tugas = data.get("nama_tugas")
    target_ruangan = data.get("target_ruangan")
    
    if not all([id_petugas, nama_tugas, target_ruangan]):
        return jsonify({"error": "id_petugas, nama_tugas, and target_ruangan are required"}), 400
        
    id_tugas = data.get("id_tugas") if request.method == "PUT" else None
    
    success = database.save_task(id_petugas, nama_tugas, target_ruangan, id_tugas)
    if success:
        return jsonify({"status": "success", "message": "Tugas saved successfully"})
    return jsonify({"error": "Failed to save tugas"}), 500

@app.route("/api/tasks/<int:id_tugas>/status", methods=["PUT"])
def update_task_state(id_tugas):
    data = request.get_json() or {}
    status_tugas = data.get("status_tugas")
    if not status_tugas:
        return jsonify({"error": "status_tugas is required"}), 400
        
    success = database.update_task_status(id_tugas, status_tugas)
    if success:
        return jsonify({"status": "success", "message": "Tugas status updated successfully"})
    return jsonify({"error": "Failed to update tugas status"}), 500


# --- Per-Node Calibration Endpoint ---
@app.route("/api/calibrate/node/<anchor_id>", methods=["POST"])
def calibrate_node(anchor_id):
    data = request.get_json() or {}
    beacon_id = data.get("beacon_id")
    
    # If no beacon_id provided, find the strongest one from latest scans
    if not beacon_id:
        with scan_store_lock:
            entry = scan_store.get(anchor_id)
            if entry and entry.get("beacons"):
                sorted_beacons = sorted(entry["beacons"], key=lambda b: b.get("rssi", -100), reverse=True)
                beacon_id = sorted_beacons[0]["beacon_id"]
                
    if not beacon_id:
        return jsonify({"error": "No active beacon found for calibration"}), 400
        
    # Get last 5 RSSI readings from DB
    try:
        readings = database.get_rssi_history(beacon_id, limit=30)
        # Filter for this anchor
        anchor_readings = [r for r in readings if r.get("anchor_id") == anchor_id]
        if not anchor_readings:
            return jsonify({"error": f"No recent RSSI logs found for anchor {anchor_id} and beacon {beacon_id}"}), 400
            
        recent_rssi = [r["rssi"] for r in anchor_readings[:5]]
        avg_rssi = sum(recent_rssi) / len(recent_rssi)
        
        # We also need old calibration to log differences
        old_ptx = -59.0
        old_n = 2.0
        anchors_db = database.get_anchors_list()
        for a in anchors_db:
            if a["anchor_id"] == anchor_id:
                old_ptx = a.get("p_tx", -59.0)
                old_n = a.get("faktor_n", 2.0)
                break
                
        # Update calibration parameters (P_tx = avg_rssi, n remains the same or default)
        new_ptx = round(avg_rssi, 2)
        database.update_anchor_calibration(anchor_id, new_ptx, old_n)
        database.save_calibration_log(anchor_id, old_ptx, new_ptx, old_n, old_n)
        
        add_log("INFO", "SYSTEM", f"Node {anchor_id} calibrated: P_tx updated from {old_ptx} dBm to {new_ptx} dBm (using beacon {beacon_id[-8:]})")
        
        return jsonify({
            "status": "success",
            "anchor_id": anchor_id,
            "beacon_id": beacon_id,
            "p_tx": new_ptx,
            "faktor_n": old_n
        })
    except Exception as e:
        return jsonify({"error": f"Calibration failed: {str(e)}"}), 500

@app.route("/api/calibrate/history", methods=["GET"])
def get_calib_history():
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"history": database.get_calibration_history(limit)})


# --- Dwelling Time Heatmap Endpoint ---
@app.route("/api/analytics/heatmap", methods=["GET"])
def get_heatmap_data():
    beacon_id = request.args.get("beacon_id")
    limit = request.args.get("limit", 500, type=int)
    
    if not beacon_id:
        return jsonify({"error": "beacon_id parameter is required"}), 400
        
    try:
        history = database.get_beacon_positions_history(beacon_id, limit)
        if not history:
            return jsonify({"heatmap": [], "count": 0, "max_value": 0})
            
        # Reverse to chronological order (database returns descending)
        history = history[::-1]
        
        grid = {} # (gx, gy) -> seconds
        
        def parse_ts(ts_str):
            try:
                return datetime.fromisoformat(ts_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                return datetime.utcnow()
                
        for i in range(1, len(history)):
            p1 = history[i-1]
            p2 = history[i]
            
            t1 = parse_ts(p1["timestamp"])
            t2 = parse_ts(p2["timestamp"])
            dt = (t2 - t1).total_seconds()
            
            # If offline / gap > 5 mins, skip
            if dt > 300:
                continue
                
            x1, y1 = p1["x"], p1["y"]
            x2, y2 = p2["x"], p2["y"]
            dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            # Stationary if moved < 0.5m
            if dist < 0.5:
                # Round to nearest 0.5m cell
                gx = round(x2 * 2) / 2.0
                gy = round(y2 * 2) / 2.0
                grid[(gx, gy)] = grid.get((gx, gy), 0.0) + dt
                
        heatmap_list = [{"x": k[0], "y": k[1], "value": round(v, 1)} for k, v in grid.items()]
        max_val = max([h["value"] for h in heatmap_list]) if heatmap_list else 0.0
        
        return jsonify({
            "heatmap": heatmap_list,
            "max_value": round(max_val, 1),
            "count": len(heatmap_list)
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve heatmap: {str(e)}"}), 500


# --- Database Pruning Settings API ---
@app.route("/api/pruning/config", methods=["GET", "PUT"])
def get_update_pruning_config():
    if request.method == "GET":
        return jsonify(database.get_pruning_config())
        
    data = request.get_json() or {}
    retention_days = data.get("retention_days")
    if not isinstance(retention_days, int) or retention_days <= 0:
        return jsonify({"error": "retention_days must be a positive integer"}), 400
        
    success = database.update_pruning_config(retention_days)
    if success:
        return jsonify({"status": "success", "retention_days": retention_days})
    return jsonify({"error": "Failed to update pruning config"}), 500

@app.route("/api/pruning/run", methods=["POST"])
def trigger_manual_pruning():
    cfg = database.get_pruning_config()
    retention_days = cfg.get("retention_days", 30)
    
    success = database.execute_pruning(retention_days)
    if success:
        return jsonify({"status": "success", "message": f"Database pruned successfully. Data older than {retention_days} days cleared."})
    return jsonify({"error": "Failed to prune database"}), 500


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
        
        # Start background jobs scheduler
        try:
            scheduler.start_scheduler()
        except Exception as e:
            print(f"Error starting scheduler: {e}")
            add_log("ERROR", "SYSTEM", f"Gagal menjalankan scheduler: {str(e)}")

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
