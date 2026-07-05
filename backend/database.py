# backend/database.py
import os
import requests
from dotenv import load_dotenv

# Load env variables from root directory .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

DATABASE_URL = os.getenv("DATABASE_URL")
NEON_API_KEY = os.getenv("NEON_API_KEY")

def is_http_mode():
    """Detect if we should connect using HTTP (REST API / PostgREST) or TCP (psycopg2)."""
    return DATABASE_URL and (DATABASE_URL.startswith("http://") or DATABASE_URL.startswith("https://"))

# --- HTTP Mode Functions ---
def get_http_headers(table=None):
    headers = {
        "Content-Type": "application/json",
    }
    if NEON_API_KEY:
        headers["Authorization"] = f"Bearer {NEON_API_KEY}"
    if table in ["anchors", "beacons"]:
        # PostgREST resolution=merge-duplicates acts like ON CONFLICT DO UPDATE
        headers["Prefer"] = "resolution=merge-duplicates"
    return headers

def http_post(table: str, data: dict):
    if not DATABASE_URL:
        return None
    url = f"{DATABASE_URL.rstrip('/')}/{table}"
    try:
        response = requests.post(url, json=data, headers=get_http_headers(table), timeout=5)
        response.raise_for_status()
        return response.json() if response.content else True
    except Exception as e:
        print(f"NeonDB HTTP POST Error ({table}): {e}")
        return None

def http_get(table: str, params: dict = None):
    if not DATABASE_URL:
        return []
    url = f"{DATABASE_URL.rstrip('/')}/{table}"
    try:
        response = requests.get(url, params=params, headers=get_http_headers(), timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"NeonDB HTTP GET Error ({table}): {e}")
        return []

# --- psycopg2 TCP Mode Connection ---
def get_tcp_connection():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        # Standardize prefix for psycopg2
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)
    except Exception as e:
        print(f"NeonDB TCP Connection Error: {e}")
        return None

# --- Unified Public Interface ---
def save_anchor(anchor_id, x, y, label):
    if is_http_mode():
        payload = {
            "anchor_id": anchor_id,
            "x": x,
            "y": y,
            "label": label
        }
        return http_post("anchors", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO anchors (anchor_id, x, y, label) 
                    VALUES (%s, %s, %s, %s) 
                    ON CONFLICT (anchor_id) 
                    DO UPDATE SET x = EXCLUDED.x, y = EXCLUDED.y, label = EXCLUDED.label, updated_at = CURRENT_TIMESTAMP;
                """, (anchor_id, x, y, label))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_anchor error: {e}")
            return None
        finally:
            conn.close()

def save_beacon(beacon_id, name):
    if is_http_mode():
        payload = {
            "beacon_id": beacon_id,
            "name": name
        }
        return http_post("beacons", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO beacons (beacon_id, name) 
                    VALUES (%s, %s) 
                    ON CONFLICT (beacon_id) DO NOTHING;
                """, (beacon_id, name))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_beacon error: {e}")
            return None
        finally:
            conn.close()

def save_rssi_log(anchor_id, beacon_id, rssi, tx_power, distance, timestamp):
    ts_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
    if is_http_mode():
        payload = {
            "anchor_id": anchor_id,
            "beacon_id": beacon_id,
            "rssi": rssi,
            "tx_power": tx_power,
            "distance": distance,
            "timestamp": ts_str
        }
        return http_post("rssi_logs", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO rssi_logs (anchor_id, beacon_id, rssi, tx_power, distance, timestamp) 
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (anchor_id, beacon_id, rssi, tx_power, distance, timestamp))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_rssi_log error: {e}")
            return None
        finally:
            conn.close()

def save_beacon_position(beacon_id, x, y, error, anchors_used, timestamp):
    ts_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
    if is_http_mode():
        payload = {
            "beacon_id": beacon_id,
            "x": x,
            "y": y,
            "error": error,
            "anchors_used": anchors_used,
            "timestamp": ts_str
        }
        return http_post("beacon_positions", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO beacon_positions (beacon_id, x, y, error, anchors_used, timestamp) 
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (beacon_id, x, y, error, anchors_used, timestamp))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_beacon_position error: {e}")
            return None
        finally:
            conn.close()

def save_system_log(level, source, message, data=None):
    import json
    if is_http_mode():
        payload = {
            "level": level,
            "source": source,
            "message": message,
            "data": data
        }
        return http_post("system_logs", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_logs (level, source, message, data) 
                    VALUES (%s, %s, %s, %s);
                """, (level, source, message, json.dumps(data) if data is not None else None))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_system_log error: {e}")
            return None
        finally:
            conn.close()

def get_beacon_positions_history(beacon_id, limit=100):
    if is_http_mode():
        params = {
            "beacon_id": f"eq.{beacon_id}",
            "order": "timestamp.desc",
            "limit": limit
        }
        return http_get("beacon_positions", params)
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT position_id, beacon_id, x, y, error, anchors_used, timestamp 
                    FROM beacon_positions 
                    WHERE beacon_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s;
                """, (beacon_id, limit))
                results = cur.fetchall()
                for r in results:
                    r["timestamp"] = r["timestamp"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_beacon_positions_history error: {e}")
            return []
        finally:
            conn.close()

def get_rssi_history(beacon_id, limit=100):
    if is_http_mode():
        params = {
            "beacon_id": f"eq.{beacon_id}",
            "order": "timestamp.desc",
            "limit": limit
        }
        return http_get("rssi_logs", params)
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT log_id, anchor_id, beacon_id, rssi, tx_power, distance, timestamp 
                    FROM rssi_logs 
                    WHERE beacon_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT %s;
                """, (beacon_id, limit))
                results = cur.fetchall()
                for r in results:
                    r["timestamp"] = r["timestamp"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_rssi_history error: {e}")
            return []
        finally:
            conn.close()
