import requests
import time
import math

# Anchor positions in meters
# scanner-01: (0, 0)
# scanner-02: (10, 0)
# scanner-03: (5, 8)
anchors = {
    "scanner-01": [0.0, 0.0],
    "scanner-02": [10.0, 0.0],
    "scanner-03": [5.0, 8.0]
}

# Target beacon info
beacon_id = "AA:BB:CC:DD:EE:FF"
# Physical position of the beacon to simulate (in meters)
target_x = 4.5
target_y = 3.5

n = 2.0  # Path loss exponent
tx_power = -59  # TX power at 1 meter

print(f"Starting BLE Room Positioning System simulator...")
print(f"Simulating beacon {beacon_id} at position ({target_x}, {target_y})")

while True:
    for aid, pos in anchors.items():
        # Calculate distance
        dist = math.sqrt((target_x - pos[0])**2 + (target_y - pos[1])**2)
        # Calculate RSSI using path loss model: RSSI = TX - 10 * n * log10(d)
        rssi = int(tx_power - 10 * n * math.log10(max(0.1, dist)))
        
        payload = {
            "anchor_id": aid,
            "anchor_pos": pos,
            "timestamp": int(time.time() * 1000),
            "calibration_mode": False,
            "beacons": [
                {
                    "beacon_id": beacon_id,
                    "rssi": rssi,
                    "tx_power": tx_power
                }
            ]
        }
        
        try:
            res = requests.post("http://127.0.0.1:5000/api/scan", json=payload)
            if res.status_code == 200:
                print(f"Reported {aid} scan: distance={dist:.2f}m, rssi={rssi}dBm -> {res.json()}")
            else:
                print(f"Failed to report {aid}: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Error connecting to backend for {aid}: {e}")
            
    time.sleep(4)
