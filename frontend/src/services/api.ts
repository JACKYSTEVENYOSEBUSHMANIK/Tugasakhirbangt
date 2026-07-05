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

// Get recent event logs
export const getLogs = async (limit = 100) => {
  const response = await api.get(`/logs?limit=${limit}`);
  return response.data;
};

export default api;
