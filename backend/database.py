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

# --- Shift Kerja CRUD ---
def save_shift(nama_shift, jam_mulai, jam_selesai, id_shift=None):
    if is_http_mode():
        payload = {
            "nama_shift": nama_shift,
            "jam_mulai": jam_mulai,
            "jam_selesai": jam_selesai
        }
        if id_shift:
            return http_patch("shift_kerja", {"id_shift": f"eq.{id_shift}"}, payload)
        return http_post("shift_kerja", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                if id_shift:
                    cur.execute("""
                        UPDATE shift_kerja 
                        SET nama_shift = %s, jam_mulai = %s, jam_selesai = %s 
                        WHERE id_shift = %s;
                    """, (nama_shift, jam_mulai, jam_selesai, id_shift))
                else:
                    cur.execute("""
                        INSERT INTO shift_kerja (nama_shift, jam_mulai, jam_selesai) 
                        VALUES (%s, %s, %s);
                    """, (nama_shift, jam_mulai, jam_selesai))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_shift error: {e}")
            return None
        finally:
            conn.close()

def get_shifts():
    if is_http_mode():
        return http_get("shift_kerja", {"order": "id_shift.asc"})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id_shift, nama_shift, jam_mulai, jam_selesai FROM shift_kerja ORDER BY id_shift ASC;")
                results = cur.fetchall()
                for r in results:
                    r["jam_mulai"] = str(r["jam_mulai"])
                    r["jam_selesai"] = str(r["jam_selesai"])
                return results
        except Exception as e:
            print(f"NeonDB TCP get_shifts error: {e}")
            return []
        finally:
            conn.close()

def delete_shift(id_shift):
    if is_http_mode():
        return http_delete("shift_kerja", {"id_shift": f"eq.{id_shift}"})
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM shift_kerja WHERE id_shift = %s;", (id_shift,))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP delete_shift error: {e}")
            return None
        finally:
            conn.close()

# --- Petugas CRUD ---
def save_petugas(nama, beacon_id, id_shift, id_petugas=None):
    # Set to None if empty string
    b_id = beacon_id if beacon_id else None
    s_id = id_shift if id_shift else None
    
    if is_http_mode():
        if b_id:
            save_beacon(b_id, f"Beacon {b_id[-8:]}")
        payload = {
            "nama": nama,
            "beacon_id": b_id,
            "id_shift": s_id
        }
        if id_petugas:
            return http_patch("petugas", {"id_petugas": f"eq.{id_petugas}"}, payload)
        return http_post("petugas", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                if b_id:
                    cur.execute("""
                        INSERT INTO beacons (beacon_id, name)
                        VALUES (%s, %s)
                        ON CONFLICT (beacon_id) DO NOTHING;
                    """, (b_id, f"Beacon {b_id[-8:]}"))
                if id_petugas:
                    cur.execute("""
                        UPDATE petugas 
                        SET nama = %s, beacon_id = %s, id_shift = %s 
                        WHERE id_petugas = %s;
                    """, (nama, b_id, s_id, id_petugas))
                else:
                    cur.execute("""
                        INSERT INTO petugas (nama, beacon_id, id_shift) 
                        VALUES (%s, %s, %s);
                    """, (nama, b_id, s_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_petugas error: {e}")
            return None
        finally:
            conn.close()

def get_petugas_list():
    if is_http_mode():
        # Using PostgREST resource embedding to fetch shift details
        return http_get("petugas", {"select": "*,shift_kerja(*)", "order": "id_petugas.asc"})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT p.id_petugas, p.nama, p.beacon_id, p.id_shift, p.created_at,
                           s.nama_shift, s.jam_mulai, s.jam_selesai
                    FROM petugas p
                    LEFT JOIN shift_kerja s ON p.id_shift = s.id_shift
                    ORDER BY p.id_petugas ASC;
                """)
                results = cur.fetchall()
                for r in results:
                    r["created_at"] = r["created_at"].isoformat()
                    if r.get("id_shift"):
                        r["shift_kerja"] = {
                            "id_shift": r["id_shift"],
                            "nama_shift": r["nama_shift"],
                            "jam_mulai": str(r["jam_mulai"]),
                            "jam_selesai": str(r["jam_selesai"])
                        }
                    else:
                        r["shift_kerja"] = None
                    if "jam_mulai" in r: del r["jam_mulai"]
                    if "jam_selesai" in r: del r["jam_selesai"]
                return results
        except Exception as e:
            print(f"NeonDB TCP get_petugas_list error: {e}")
            return []
        finally:
            conn.close()

def delete_petugas(id_petugas):
    if is_http_mode():
        return http_delete("petugas", {"id_petugas": f"eq.{id_petugas}"})
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM petugas WHERE id_petugas = %s;", (id_petugas,))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP delete_petugas error: {e}")
            return None
        finally:
            conn.close()

# --- Tugas Petugas CRUD ---
def save_task(id_petugas, nama_tugas, target_ruangan, id_tugas=None):
    if is_http_mode():
        payload = {
            "id_petugas": id_petugas,
            "nama_tugas": nama_tugas,
            "target_ruangan": target_ruangan
        }
        if id_tugas:
            return http_patch("tugas_petugas", {"id_tugas": f"eq.{id_tugas}"}, payload)
        return http_post("tugas_petugas", payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                if id_tugas:
                    cur.execute("""
                        UPDATE tugas_petugas 
                        SET id_petugas = %s, nama_tugas = %s, target_ruangan = %s 
                        WHERE id_tugas = %s;
                    """, (id_petugas, nama_tugas, target_ruangan, id_tugas))
                else:
                    cur.execute("""
                        INSERT INTO tugas_petugas (id_petugas, nama_tugas, target_ruangan) 
                        VALUES (%s, %s, %s);
                    """, (id_petugas, nama_tugas, target_ruangan))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP save_task error: {e}")
            return None
        finally:
            conn.close()

def get_tasks(limit=100):
    if is_http_mode():
        return http_get("tugas_petugas", {"select": "*,petugas(*)", "order": "id_tugas.desc", "limit": limit})
    else:
        from psycopg2.extras import RealDictCursor
        conn = get_tcp_connection()
        if not conn: return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT t.id_tugas, t.id_petugas, t.nama_tugas, t.target_ruangan, t.status_tugas, 
                           t.waktu_mulai, t.waktu_selesai, p.nama as petugas_nama, p.beacon_id
                    FROM tugas_petugas t
                    LEFT JOIN petugas p ON t.id_petugas = p.id_petugas
                    ORDER BY t.id_tugas DESC
                    LIMIT %s;
                """, (limit,))
                results = cur.fetchall()
                for r in results:
                    if r["waktu_mulai"]: r["waktu_mulai"] = r["waktu_mulai"].isoformat()
                    if r["waktu_selesai"]: r["waktu_selesai"] = r["waktu_selesai"].isoformat()
                    r["petugas"] = {
                        "id_petugas": r["id_petugas"],
                        "nama": r["petugas_nama"],
                        "beacon_id": r["beacon_id"]
                    }
                return results
        except Exception as e:
            print(f"NeonDB TCP get_tasks error: {e}")
            return []
        finally:
            conn.close()

def update_task_status(id_tugas, status_tugas, waktu_mulai=None, waktu_selesai=None):
    payload = {"status_tugas": status_tugas}
    if waktu_mulai:
        payload["waktu_mulai"] = waktu_mulai.isoformat() if hasattr(waktu_mulai, "isoformat") else str(waktu_mulai)
    if waktu_selesai:
        payload["waktu_selesai"] = waktu_selesai.isoformat() if hasattr(waktu_selesai, "isoformat") else str(waktu_selesai)
        
    if is_http_mode():
        return http_patch("tugas_petugas", {"id_tugas": f"eq.{id_tugas}"}, payload)
    else:
        conn = get_tcp_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                if status_tugas == "On Progress":
                    cur.execute("""
                        UPDATE tugas_petugas 
                        SET status_tugas = %s, waktu_mulai = COALESCE(waktu_mulai, %s)
                        WHERE id_tugas = %s;
                    """, (status_tugas, waktu_mulai or datetime.utcnow(), id_tugas))
                elif status_tugas == "Completed":
                    cur.execute("""
                        UPDATE tugas_petugas 
                        SET status_tugas = %s, waktu_selesai = COALESCE(waktu_selesai, %s)
                        WHERE id_tugas = %s;
                    """, (status_tugas, waktu_selesai or datetime.utcnow(), id_tugas))
                else:
                    cur.execute("""
                        UPDATE tugas_petugas 
                        SET status_tugas = %s 
                        WHERE id_tugas = %s;
                    """, (status_tugas, id_tugas))
            conn.commit()
            return True
        except Exception as e:
            print(f"NeonDB TCP update_task_status error: {e}")
            return None
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

def is_petugas_on_shift(beacon_id):
    import datetime
    # 1. Fetch shift info for officer linked to beacon_id
    if is_http_mode():
        # Get officer matching beacon_id
        petugas = http_get("petugas", {"beacon_id": f"eq.{beacon_id}", "select": "*,shift_kerja(*)"})
        if not petugas or not petugas[0].get("shift_kerja"):
            # If no shift assigned, default to True (always track)
            return True
        shift = petugas[0]["shift_kerja"]
        jam_mulai_str = shift["jam_mulai"]
        jam_selesai_str = shift["jam_selesai"]
    else:
        conn = get_tcp_connection()
        if not conn: return True
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT s.jam_mulai, s.jam_selesai 
                    FROM petugas p
                    JOIN shift_kerja s ON p.id_shift = s.id_shift
                    WHERE p.beacon_id = %s;
                """, (beacon_id,))
                res = cur.fetchone()
                if not res:
                    return True
                jam_mulai_str = str(res[0])
                jam_selesai_str = str(res[1])
        except Exception as e:
            print(f"Error checking shift: {e}")
            return True
        finally:
            conn.close()
            
    # Parse times
    try:
        def parse_time(t_str):
            # Parse '08:00:00' or similar
            parts = list(map(int, t_str.split(':')))
            return datetime.time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)
        
        start_time = parse_time(jam_mulai_str)
        end_time = parse_time(jam_selesai_str)
        now_time = datetime.datetime.now().time()
        
        if start_time <= end_time:
            return start_time <= now_time <= end_time
        else: # midnight crossing shift, e.g. 22:00 to 06:00
            return now_time >= start_time or now_time <= end_time
    except Exception as e:
        print(f"Error parsing shift times: {e}")
        return True


