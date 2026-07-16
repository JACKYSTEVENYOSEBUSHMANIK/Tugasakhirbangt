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

def http_patch(table: str, params: dict, data: dict):
    if not DATABASE_URL:
        return None
    url = f"{DATABASE_URL.rstrip('/')}/{table}"
    try:
        response = requests.patch(url, json=data, params=params, headers=get_http_headers(), timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"NeonDB HTTP PATCH Error ({table}): {e}")
        return None

def http_delete(table: str, params: dict):
    if not DATABASE_URL:
        return None
    url = f"{DATABASE_URL.rstrip('/')}/{table}"
    try:
        response = requests.delete(url, params=params, headers=get_http_headers(), timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"NeonDB HTTP DELETE Error ({table}): {e}")
        return None

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

def get_beacons_list():
    if is_http_mode():
        return http_get("beacons", {"order": "created_at.desc"})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT beacon_id, name, created_at FROM beacons ORDER BY created_at DESC;")
                results = cur.fetchall()
                for r in results:
                    r["created_at"] = r["created_at"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_beacons_list error: {e}")
            return []
        finally:
            conn.close()

def get_tracked_beacons():
    """Beacons that have at least one saved position — i.e. could plausibly show heatmap data."""
    if is_http_mode():
        recent = http_get("beacon_positions", {"select": "beacon_id", "order": "timestamp.desc", "limit": 2000}) or []
        seen = []
        seen_set = set()
        for row in recent:
            bid = row.get("beacon_id")
            if bid and bid not in seen_set:
                seen_set.add(bid)
                seen.append(bid)
        names = {b["beacon_id"]: b.get("name") for b in (get_beacons_list() or [])}
        return [{"beacon_id": bid, "name": names.get(bid) or bid} for bid in seen]
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT ON (bp.beacon_id) bp.beacon_id, b.name, bp.timestamp AS last_seen
                    FROM beacon_positions bp
                    LEFT JOIN beacons b ON b.beacon_id = bp.beacon_id
                    ORDER BY bp.beacon_id, bp.timestamp DESC;
                """)
                results = cur.fetchall()
                results.sort(key=lambda r: r["last_seen"], reverse=True)
                for r in results:
                    r["last_seen"] = r["last_seen"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_tracked_beacons error: {e}")
            return []
        finally:
            conn.close()

def upsert_device(beacon_id, name):
    """Create or rename a device entry (user-driven, overwrites the name)."""
    if is_http_mode():
        payload = {"beacon_id": beacon_id, "name": name}
        return http_post("beacons", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO beacons (beacon_id, name)
                    VALUES (%s, %s)
                    ON CONFLICT (beacon_id) DO UPDATE SET name = EXCLUDED.name;
                """, (beacon_id, name))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP upsert_device error: {e}")
            return None
        finally:
            conn.close()

def delete_beacon(beacon_id):
    if is_http_mode():
        return http_delete("beacons", {"beacon_id": f"eq.{beacon_id}"})
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM beacons WHERE beacon_id = %s;", (beacon_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP delete_beacon error: {e}")
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

# --- Calibration Log ---
def save_calibration_log(anchor_id, p_tx_old, p_tx_new, faktor_n_old, faktor_n_new):
    if is_http_mode():
        payload = {
            "anchor_id": anchor_id,
            "p_tx_old": p_tx_old,
            "p_tx_new": p_tx_new,
            "faktor_n_old": faktor_n_old,
            "faktor_n_new": faktor_n_new
        }
        return http_post("calibration_log", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO calibration_log (anchor_id, p_tx_old, p_tx_new, faktor_n_old, faktor_n_new)
                    VALUES (%s, %s, %s, %s, %s);
                """, (anchor_id, p_tx_old, p_tx_new, faktor_n_old, faktor_n_new))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_calibration_log error: {e}")
            return None
        finally:
            conn.close()

def get_calibration_history(limit=50):
    if is_http_mode():
        return http_get("calibration_log", {"order": "calibrated_at.desc", "limit": limit})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT log_id, anchor_id, p_tx_old, p_tx_new, faktor_n_old, faktor_n_new, calibrated_at 
                    FROM calibration_log 
                    ORDER BY calibrated_at DESC 
                    LIMIT %s;
                """, (limit,))
                results = cur.fetchall()
                for r in results:
                    r["calibrated_at"] = r["calibrated_at"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_calibration_history error: {e}")
            return []
        finally:
            conn.close()

# --- Anchor Calibration values (PRD: F1 Signal Calibrator) ---
def update_anchor_calibration(anchor_id, p_tx, faktor_n):
    if is_http_mode():
        # First check if anchor exists
        anchors = http_get("anchors", {"anchor_id": f"eq.{anchor_id}"})
        payload = {"p_tx": p_tx, "faktor_n": faktor_n}
        if anchors:
            return http_patch("anchors", {"anchor_id": f"eq.{anchor_id}"}, payload)
        else:
            payload["anchor_id"] = anchor_id
            payload["x"] = 0.0
            payload["y"] = 0.0
            return http_post("anchors", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO anchors (anchor_id, x, y, p_tx, faktor_n)
                    VALUES (%s, 0.0, 0.0, %s, %s)
                    ON CONFLICT (anchor_id)
                    DO UPDATE SET p_tx = EXCLUDED.p_tx, faktor_n = EXCLUDED.faktor_n, updated_at = CURRENT_TIMESTAMP;
                """, (anchor_id, p_tx, faktor_n))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP update_anchor_calibration error: {e}")
            return None
        finally:
            conn.close()

def get_anchors_list():
    if is_http_mode():
        return http_get("anchors", {"order": "anchor_id.asc"})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT anchor_id, x, y, label, p_tx, faktor_n FROM anchors ORDER BY anchor_id ASC;")
                return cur.fetchall()
        except Exception as e:
            print(f"NeonDB TCP get_anchors_list error: {e}")
            return []
        finally:
            conn.close()

# --- Pruning Config CRUD ---
def get_pruning_config():
    if is_http_mode():
        cfgs = http_get("pruning_config", {"id": "eq.1"})
        if cfgs:
            return cfgs[0]
        # Return default if missing
        return {"retention_days": 30, "last_pruned_at": None}
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return {"retention_days": 30, "last_pruned_at": None}
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT retention_days, last_pruned_at FROM pruning_config WHERE id = 1;")
                res = cur.fetchone()
                if res:
                    if res["last_pruned_at"]: res["last_pruned_at"] = res["last_pruned_at"].isoformat()
                    return res
                return {"retention_days": 30, "last_pruned_at": None}
        except Exception as e:
            print(f"NeonDB TCP get_pruning_config error: {e}")
            return {"retention_days": 30, "last_pruned_at": None}
        finally:
            conn.close()

def update_pruning_config(retention_days):
    if is_http_mode():
        cfgs = http_get("pruning_config", {"id": "eq.1"})
        payload = {"retention_days": retention_days}
        if cfgs:
            return http_patch("pruning_config", {"id": "eq.1"}, payload)
        else:
            payload["id"] = 1
            return http_post("pruning_config", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pruning_config (id, retention_days)
                    VALUES (1, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET retention_days = EXCLUDED.retention_days, updated_at = CURRENT_TIMESTAMP;
                """, (retention_days,))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP update_pruning_config error: {e}")
            return None
        finally:
            conn.close()

def update_last_pruned_time():
    import datetime
    now_str = datetime.datetime.utcnow().isoformat()
    if is_http_mode():
        return http_patch("pruning_config", {"id": "eq.1"}, {"last_pruned_at": now_str})
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE pruning_config SET last_pruned_at = %s WHERE id = 1;", (datetime.datetime.utcnow(),))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP update_last_pruned_time error: {e}")
            return None
        finally:
            conn.close()

# --- Daily Summary & Pruning logic ---
def save_daily_summary(beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi):
    if is_http_mode():
        payload = {
            "beacon_id": beacon_id,
            "summary_date": str(summary_date),
            "total_positions": total_positions,
            "avg_x": avg_x,
            "avg_y": avg_y,
            "avg_error": avg_error,
            "total_rssi_readings": total_rssi_readings,
            "avg_rssi": avg_rssi
        }
        return http_post("daily_summary", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO daily_summary (beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (beacon_id, summary_date) DO UPDATE SET
                        total_positions = EXCLUDED.total_positions,
                        avg_x = EXCLUDED.avg_x,
                        avg_y = EXCLUDED.avg_y,
                        avg_error = EXCLUDED.avg_error,
                        total_rssi_readings = EXCLUDED.total_rssi_readings,
                        avg_rssi = EXCLUDED.avg_rssi;
                """, (beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_daily_summary error: {e}")
            return None
        finally:
            conn.close()

def get_daily_summaries(beacon_id=None, limit=100):
    if is_http_mode():
        params = {"order": "summary_date.desc", "limit": limit}
        if beacon_id:
            params["beacon_id"] = f"eq.{beacon_id}"
        return http_get("daily_summary", params)
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if beacon_id:
                    cur.execute("""
                        SELECT summary_id, beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi 
                        FROM daily_summary 
                        WHERE beacon_id = %s 
                        ORDER BY summary_date DESC 
                        LIMIT %s;
                    """, (beacon_id, limit))
                else:
                    cur.execute("""
                        SELECT summary_id, beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi 
                        FROM daily_summary 
                        ORDER BY summary_date DESC 
                        LIMIT %s;
                    """, (limit,))
                results = cur.fetchall()
                for r in results:
                    r["summary_date"] = r["summary_date"].isoformat()
                return results
        except Exception as e:
            print(f"NeonDB TCP get_daily_summaries error: {e}")
            return []
        finally:
            conn.close()

def execute_pruning(days):
    import datetime
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    cutoff_date = cutoff.date()
    cutoff_str = cutoff.isoformat()
    
    # 1. Aggregate and prune rssi_logs and beacon_positions
    if is_http_mode():
        # PostgREST DELETE calls
        # Since we want to perform aggregation before deletion:
        # Fetch data to aggregate: we look for days that have logs but no summaries yet
        # For simplicity in http mode, we fetch records from rssi_logs and beacon_positions that are older than `days`
        # and create their summaries in Python, then delete.
        # Let's fetch all raw scans older than cutoff
        old_positions = http_get("beacon_positions", {"timestamp": f"lt.{cutoff_str}"})
        old_rssi = http_get("rssi_logs", {"timestamp": f"lt.{cutoff_str}"})
        
        # Group by beacon and date
        groups = {}
        for pos in old_positions:
            bid = pos.get("beacon_id")
            dt_str = pos.get("timestamp")[:10]  # YYYY-MM-DD
            if (bid, dt_str) not in groups:
                groups[(bid, dt_str)] = {"pos_x": [], "pos_y": [], "error": [], "rssi": []}
            groups[(bid, dt_str)]["pos_x"].append(pos.get("x"))
            groups[(bid, dt_str)]["pos_y"].append(pos.get("y"))
            groups[(bid, dt_str)]["error"].append(pos.get("error", 0.0))
            
        for log in old_rssi:
            bid = log.get("beacon_id")
            dt_str = log.get("timestamp")[:10]
            if (bid, dt_str) not in groups:
                groups[(bid, dt_str)] = {"pos_x": [], "pos_y": [], "error": [], "rssi": []}
            groups[(bid, dt_str)]["rssi"].append(log.get("rssi"))
            
        # Create summary rows
        for (bid, dt_str), data in groups.items():
            total_pos = len(data["pos_x"])
            avg_x = sum(data["pos_x"]) / total_pos if total_pos > 0 else 0.0
            avg_y = sum(data["pos_y"]) / total_pos if total_pos > 0 else 0.0
            avg_err = sum(data["error"]) / total_pos if total_pos > 0 else 0.0
            total_rssi = len(data["rssi"])
            avg_r = sum(data["rssi"]) / total_rssi if total_rssi > 0 else 0.0
            
            save_daily_summary(bid, dt_str, total_pos, avg_x, avg_y, avg_err, total_rssi, avg_r)
            
        # Perform deletions
        http_delete("beacon_positions", {"timestamp": f"lt.{cutoff_str}"})
        http_delete("rssi_logs", {"timestamp": f"lt.{cutoff_str}"})
        update_last_pruned_time()
        return True
    else:
        conn = get_tcp_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                # Get list of unique (beacon_id, date) combinations from older data
                cur.execute("""
                    SELECT DISTINCT beacon_id, DATE(timestamp) as dt 
                    FROM beacon_positions 
                    WHERE timestamp < %s;
                """, (cutoff,))
                pairs = cur.fetchall()
                
                for bid, dt in pairs:
                    # Calculate aggregate values
                    cur.execute("""
                        SELECT COUNT(*), AVG(x), AVG(y), AVG(error) 
                        FROM beacon_positions 
                        WHERE beacon_id = %s AND DATE(timestamp) = %s;
                    """, (bid, dt))
                    pos_count, avg_x, avg_y, avg_error = cur.fetchone()
                    
                    cur.execute("""
                        SELECT COUNT(*), AVG(rssi) 
                        FROM rssi_logs 
                        WHERE beacon_id = %s AND DATE(timestamp) = %s;
                    """, (bid, dt))
                    rssi_count, avg_rssi = cur.fetchone()
                    
                    # Insert into daily_summary
                    cur.execute("""
                        INSERT INTO daily_summary (beacon_id, summary_date, total_positions, avg_x, avg_y, avg_error, total_rssi_readings, avg_rssi)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (beacon_id, summary_date) DO UPDATE SET
                            total_positions = EXCLUDED.total_positions,
                            avg_x = EXCLUDED.avg_x,
                            avg_y = EXCLUDED.avg_y,
                            avg_error = EXCLUDED.avg_error,
                            total_rssi_readings = EXCLUDED.total_rssi_readings,
                            avg_rssi = EXCLUDED.avg_rssi;
                    """, (bid, dt, pos_count or 0, avg_x or 0.0, avg_y or 0.0, avg_error or 0.0, rssi_count or 0, avg_rssi or 0.0))
                
                # Delete old records
                cur.execute("DELETE FROM beacon_positions WHERE timestamp < %s;", (cutoff,))
                cur.execute("DELETE FROM rssi_logs WHERE timestamp < %s;", (cutoff,))
            conn.commit()
            update_last_pruned_time()
            return True
        except Exception as e:
            print(f"NeonDB TCP execute_pruning error: {e}")
            return False
        finally:
            conn.close()

