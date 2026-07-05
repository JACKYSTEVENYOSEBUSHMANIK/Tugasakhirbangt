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
