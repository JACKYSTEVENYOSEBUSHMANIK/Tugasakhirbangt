# backend/signal_monitor.py
import time
from collections import deque
import numpy as np
import database

# Cache of last 15 RSSI and position readings per beacon for anomaly detection
# beacon_id -> anchor_id -> deque of (timestamp, rssi)
rssi_windows = {}
# beacon_id -> deque of (timestamp, x, y)
position_windows = {}

# Cooldown to avoid flooding alerts (alert once per 30 seconds per beacon/anchor)
alert_cooldowns = {}

def update_monitor_data(beacon_id, pos_res, scan_entry):
    """Called after each scan is received to update signal history and check for anomalies."""
    now = time.time()
    
    # 1. Update Position history
    pos = pos_res.get("position")
    if pos:
        if beacon_id not in position_windows:
            position_windows[beacon_id] = deque(maxlen=10)
        position_windows[beacon_id].append((now, pos[0], pos[1]))
        
    # 2. Update RSSI history per anchor
    anchor_id = scan_entry.get("anchor_id")
    for b in scan_entry.get("beacons", []):
        bid = b.get("beacon_id")
        rssi = b.get("rssi")
        if not bid or rssi is None:
            continue
            
        if bid not in rssi_windows:
            rssi_windows[bid] = {}
        if anchor_id not in rssi_windows[bid]:
            rssi_windows[bid][anchor_id] = deque(maxlen=15)
            
        rssi_windows[bid][anchor_id].append((now, rssi))
        
    # 3. Check for anomalies
    check_anomalies(beacon_id, anchor_id)

def check_anomalies(beacon_id, anchor_id):
    now = time.time()
    
    # Check cooldown
    cooldown_key = (beacon_id, anchor_id)
    if cooldown_key in alert_cooldowns and now - alert_cooldowns[cooldown_key] < 30:
        return
        
    pos_win = position_windows.get(beacon_id)
    if not pos_win or len(pos_win) < 5:
        return
        
    rssi_win = rssi_windows.get(beacon_id, {}).get(anchor_id)
    if not rssi_win or len(rssi_win) < 8:
        return
        
    # Calculate position movement (standard deviation)
    x_coords = [p[1] for p in pos_win]
    y_coords = [p[2] for p in pos_win]
    movement = np.std(x_coords) + np.std(y_coords)
    
    # Check if officer is stationary (movement standard deviation < 0.4 meters)
    if movement < 0.4:
        # Check RSSI drop
        recent_rssi = [r[1] for r in list(rssi_win)[-3:]] # last 3 readings
        older_rssi = [r[1] for r in list(rssi_win)[:-3]]  # older readings
        
        if recent_rssi and older_rssi:
            avg_recent = np.mean(recent_rssi)
            avg_older = np.mean(older_rssi)
            
            # Anomaly: RSSI drops by more than 15 dBm
            if avg_recent < (avg_older - 15):
                drop_amount = int(avg_older - avg_recent)
                message = f"Potensi interferensi terdeteksi pada node {anchor_id} untuk perangkat {beacon_id[-8:]}. Sinyal turun {drop_amount} dBm saat perangkat diam."
                print(f"[ANOMALY] {message}")
                
                # Save to database system logs
                database.save_system_log(
                    "WARN", 
                    "SYSTEM", 
                    message, 
                    {"beacon_id": beacon_id, "anchor_id": anchor_id, "drop_db": drop_amount}
                )
                
                # Set cooldown
                alert_cooldowns[cooldown_key] = now
