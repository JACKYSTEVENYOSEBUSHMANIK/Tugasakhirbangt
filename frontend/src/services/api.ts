import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Get current beacon positions (trilateration results)
export const getPositions = async () => {
  const response = await api.get('/positions');
  return response.data;
};

// Get anchor configurations and status
export const getAnchors = async () => {
  const response = await api.get('/anchors');
  return response.data;
};

// Update anchor positions
export const updateAnchors = async (anchors: Array<{ anchor_id: string; x: number; y: number }>) => {
  const response = await api.put('/anchors', { anchors });
  return response.data;
};

// Get latest raw scan data
export const getScanData = async () => {
  const response = await api.get('/scan-data');
  return response.data;
};

// Get calibration parameters
export const getCalibration = async () => {
  const response = await api.get('/calibrate');
  return response.data;
};

// Update calibration parameters
export const updateCalibration = async (params: {
  path_loss_exponent?: number;
  tx_power_dbm?: number;
  min_rssi_threshold?: number;
  scan_ttl_seconds?: number;
}) => {
  const response = await api.post('/calibrate', params);
  return response.data;
};

// Health check
export const getHealth = async () => {
  const response = await api.get('/health');
  return response.data;
};

// Get full config
export const getFullConfig = async () => {
  const response = await api.get('/config');
  return response.data;
};

// Update room dimensions
export const updateRoom = async (dims: { width_m: number; height_m: number }) => {
  const response = await api.put('/room', dims);
  return response.data;
};

// Zones (ruangan) API
export const getZones = async () => {
  const response = await api.get('/zones');
  return response.data;
};

export const createZone = async (zone: { name: string; x_min: number; x_max: number; y_min: number; y_max: number }) => {
  const response = await api.post('/zones', zone);
  return response.data;
};

export const deleteZone = async (name: string) => {
  const response = await api.delete(`/zones/${encodeURIComponent(name)}`);
  return response.data;
};

// Get recent event logs
export const getLogs = async (limit = 100) => {
  const response = await api.get(`/logs?limit=${limit}`);
  return response.data;
};

// Device (Beacon) API
export const getDevices = async () => {
  const response = await api.get('/devices');
  return response.data;
};

export const createDevice = async (device: { beacon_id: string; name?: string }) => {
  const response = await api.post('/devices', device);
  return response.data;
};

export const deleteDevice = async (beaconId: string) => {
  const response = await api.delete(`/devices/${encodeURIComponent(beaconId)}`);
  return response.data;
};

// Devices that have at least one saved position (usable candidates for the heatmap)
export const getTrackedDevices = async () => {
  const response = await api.get('/devices/tracked');
  return response.data;
};

// Per-Node Calibration API
export const calibrateNode = async (anchorId: string, beaconId?: string) => {
  const response = await api.post(`/calibrate/node/${anchorId}`, { beacon_id: beaconId });
  return response.data;
};

export const getCalibrationHistory = async () => {
  const response = await api.get('/calibrate/history');
  return response.data;
};

// Heatmap API
export const getHeatmapData = async (beaconId: string) => {
  const response = await api.get(`/analytics/heatmap?beacon_id=${beaconId}`);
  return response.data;
};

// Pruning Config API
export const getPruningConfig = async () => {
  const response = await api.get('/pruning/config');
  return response.data;
};

export const updatePruningConfig = async (retentionDays: number) => {
  const response = await api.put('/pruning/config', { retention_days: retentionDays });
  return response.data;
};

export const runPruning = async () => {
  const response = await api.post('/pruning/run');
  return response.data;
};

export default api;
