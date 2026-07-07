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

// Shift Kerja API
export const getShifts = async () => {
  const response = await api.get('/shifts');
  return response.data;
};

export const createShift = async (shift: { nama_shift: string; jam_mulai: string; jam_selesai: string }) => {
  const response = await api.post('/shifts', shift);
  return response.data;
};

export const updateShift = async (shift: { id_shift: number; nama_shift: string; jam_mulai: string; jam_selesai: string }) => {
  const response = await api.put('/shifts', shift);
  return response.data;
};

export const deleteShift = async (id: number) => {
  const response = await api.delete(`/shifts/${id}`);
  return response.data;
};

// Petugas API
export const getPetugasList = async () => {
  const response = await api.get('/petugas');
  return response.data;
};

export const createPetugas = async (petugas: { nama: string; beacon_id: string | null; id_shift: number | null }) => {
  const response = await api.post('/petugas', petugas);
  return response.data;
};

export const updatePetugas = async (petugas: { id_petugas: number; nama: string; beacon_id: string | null; id_shift: number | null }) => {
  const response = await api.put('/petugas', petugas);
  return response.data;
};

export const deletePetugas = async (id: number) => {
  const response = await api.delete(`/petugas/${id}`);
  return response.data;
};

// Tugas API
export const getTasks = async (limit = 100) => {
  const response = await api.get(`/tasks?limit=${limit}`);
  return response.data;
};

export const createTask = async (task: { id_petugas: number; nama_tugas: string; target_ruangan: string }) => {
  const response = await api.post('/tasks', task);
  return response.data;
};

export const updateTaskStatus = async (id: number, status: string) => {
  const response = await api.put(`/tasks/${id}/status`, { status_tugas: status });
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
