# backend/test_db.py
import sys
from datetime import datetime
import database

def test_neon_integration():
    print("=========================================")
    print("Testing NeonDB Integration & API Helper")
    print("=========================================")
    
    print(f"DATABASE_URL: {database.DATABASE_URL}")
    print(f"HTTP Mode active: {database.is_http_mode()}")
    print("-----------------------------------------")
    
    if database.is_http_mode():
        print("Testing HTTP connectivity via Neon Data API (PostgREST)...")
    else:
        print("Testing TCP connectivity via psycopg2 driver...")
        
    print("\n1. Testing anchor creation/upsert...")
    res_anchor = database.save_anchor("test-scanner", 1.5, 2.5, "Test Scanner Unit")
    if res_anchor:
        print("[ SUCCESS ] save_anchor success!")
    else:
        print("[ FAILED ] save_anchor failed.")
        
    print("\n2. Testing beacon creation/upsert...")
    res_beacon = database.save_beacon("FF:FF:FF:FF:FF:FF", "Test Beacon")
    if res_beacon:
        print("[ SUCCESS ] save_beacon success!")
    else:
        print("[ FAILED ] save_beacon failed.")
        
    print("\n3. Testing rssi log insertion...")
    res_rssi = database.save_rssi_log("test-scanner", "FF:FF:FF:FF:FF:FF", -60, -59, 1.12, datetime.utcnow())
    if res_rssi:
        print("[ SUCCESS ] save_rssi_log success!")
    else:
        print("[ FAILED ] save_rssi_log failed.")
        
    print("\n4. Testing beacon position insertion...")
    res_pos = database.save_beacon_position("FF:FF:FF:FF:FF:FF", 3.2, 4.5, 0.45, 3, datetime.utcnow())
    if res_pos:
        print("[ SUCCESS ] save_beacon_position success!")
    else:
        print("[ FAILED ] save_beacon_position failed.")
        
    print("\n5. Testing system log insertion...")
    res_sys = database.save_system_log("INFO", "TEST", "Test event message", {"test_key": "test_val"})
    if res_sys:
        print("[ SUCCESS ] save_system_log success!")
    else:
        print("[ FAILED ] save_system_log failed.")
        
    print("\n6. Testing reading history back...")
    pos_history = database.get_beacon_positions_history("FF:FF:FF:FF:FF:FF", limit=5)
    print(f"Found {len(pos_history)} position history rows:")
    for row in pos_history:
        print(f" - Pos: ({row.get('x')}, {row.get('y')}) @ {row.get('timestamp')}")
        
    rssi_history = database.get_rssi_history("FF:FF:FF:FF:FF:FF", limit=5)
    print(f"Found {len(rssi_history)} RSSI history rows:")
    for row in rssi_history:
        print(f" - RSSI: {row.get('rssi')} @ {row.get('timestamp')}")

    print("=========================================")
    if res_anchor and res_beacon and res_rssi and res_pos and res_sys:
        print("ALL DATABASE INTEGRATION TESTS PASSED!")
    else:
        print("SOME DB INTEGRATION TESTS FAILED. Check credentials and table configurations.")

    print("=========================================")

if __name__ == "__main__":
    test_neon_integration()
