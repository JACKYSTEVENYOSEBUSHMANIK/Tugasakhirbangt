-- SQL Schema for BLE Room Positioning System
-- Database name: pleaseorder (PostgreSQL / NeonDB)

-- 1. Table for Anchors (BLE Scanners configuration)
CREATE TABLE IF NOT EXISTS anchors (
    anchor_id VARCHAR(50) PRIMARY KEY,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    label VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Table for Beacons (Tracked BLE devices)
CREATE TABLE IF NOT EXISTS beacons (
    beacon_id VARCHAR(50) PRIMARY KEY, -- MAC Address (e.g. AA:BB:CC:DD:EE:FF)
    name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Table for Raw Scan Logs (Historical RSSI readings from scanners)
CREATE TABLE IF NOT EXISTS rssi_logs (
    log_id BIGSERIAL PRIMARY KEY,
    anchor_id VARCHAR(50) REFERENCES anchors(anchor_id) ON DELETE CASCADE,
    beacon_id VARCHAR(50),
    rssi INT NOT NULL,
    tx_power INT NOT NULL,
    distance DOUBLE PRECISION, -- Calculated distance based on path loss model
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index to optimize querying recent logs
CREATE INDEX IF NOT EXISTS idx_rssi_logs_timestamp ON rssi_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rssi_logs_beacon ON rssi_logs (beacon_id);

-- 4. Table for Calculated Beacon Positions (Trilateration results)
CREATE TABLE IF NOT EXISTS beacon_positions (
    position_id BIGSERIAL PRIMARY KEY,
    beacon_id VARCHAR(50),
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    error DOUBLE PRECISION, -- Error margin in meters
    anchors_used INT NOT NULL, -- Number of anchors used in calculation
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index to optimize fetching historical position trajectories
CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON beacon_positions (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_beacon ON beacon_positions (beacon_id);

-- 5. Table for System Logs
CREATE TABLE IF NOT EXISTS system_logs (
    log_id BIGSERIAL PRIMARY KEY,
    level VARCHAR(10) NOT NULL, -- INFO, WARN, ERROR, SCAN
    source VARCHAR(20) NOT NULL, -- ESP, BACKEND, TRILAT, SYSTEM
    message TEXT NOT NULL,
    data JSONB, -- Additional payload data in JSON format
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index to optimize fetching recent logs
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs (timestamp DESC);

-- 6. Table for Shift Kerja (Work Shifts)
CREATE TABLE IF NOT EXISTS shift_kerja (
    id_shift SERIAL PRIMARY KEY,
    nama_shift VARCHAR(50) NOT NULL,
    jam_mulai TIME NOT NULL,
    jam_selesai TIME NOT NULL
);

-- 7. Table for Petugas (Officers)
CREATE TABLE IF NOT EXISTS petugas (
    id_petugas SERIAL PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    beacon_id VARCHAR(50) REFERENCES beacons(beacon_id) ON DELETE SET NULL,
    id_shift INT REFERENCES shift_kerja(id_shift) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Table for Tugas Petugas (Officer Tasks)
CREATE TABLE IF NOT EXISTS tugas_petugas (
    id_tugas SERIAL PRIMARY KEY,
    id_petugas INT REFERENCES petugas(id_petugas) ON DELETE CASCADE,
    nama_tugas VARCHAR(100) NOT NULL,
    target_ruangan VARCHAR(50) NOT NULL,
    status_tugas VARCHAR(20) DEFAULT 'Pending', -- Pending, On Progress, Completed
    waktu_mulai TIMESTAMP WITH TIME ZONE,
    waktu_selesai TIMESTAMP WITH TIME ZONE
);

-- 9. Table for Calibration Logs
CREATE TABLE IF NOT EXISTS calibration_log (
    log_id SERIAL PRIMARY KEY,
    anchor_id VARCHAR(50) REFERENCES anchors(anchor_id) ON DELETE CASCADE,
    p_tx_old FLOAT,
    p_tx_new FLOAT,
    faktor_n_old FLOAT,
    faktor_n_new FLOAT,
    calibrated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Table for Daily Position Summaries (for Pruned Data)
CREATE TABLE IF NOT EXISTS daily_summary (
    summary_id SERIAL PRIMARY KEY,
    beacon_id VARCHAR(50),
    summary_date DATE NOT NULL,
    total_positions INT,
    avg_x DOUBLE PRECISION,
    avg_y DOUBLE PRECISION,
    avg_error DOUBLE PRECISION,
    total_rssi_readings INT,
    avg_rssi DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_beacon_date UNIQUE (beacon_id, summary_date)
);

-- 11. Table for Database Pruning Configuration
CREATE TABLE IF NOT EXISTS pruning_config (
    id SERIAL PRIMARY KEY,
    retention_days INT DEFAULT 30,
    last_pruned_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add Calibration columns to Anchors table
ALTER TABLE anchors ADD COLUMN IF NOT EXISTS p_tx FLOAT DEFAULT -59.0;
ALTER TABLE anchors ADD COLUMN IF NOT EXISTS faktor_n FLOAT DEFAULT 2.0;

-- Populate default pruning configuration if empty
INSERT INTO pruning_config (id, retention_days)
VALUES (1, 30)
ON CONFLICT DO NOTHING;

