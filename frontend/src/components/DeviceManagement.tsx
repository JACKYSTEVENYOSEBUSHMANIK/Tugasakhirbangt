import { useState, useEffect, useMemo } from 'react';
import { getDevices, createDevice, deleteDevice } from '../services/api';

interface Device {
  beacon_id: string;
  name: string;
  created_at: string;
}

interface ScanEntry {
  anchor_id: string;
  beacons: Array<{ beacon_id: string; rssi: number; name?: string }>;
}

interface DetectedBeacon {
  beacon_id: string;
  bestRssi: number;
  reportedName?: string;
}

interface DeviceManagementProps {
  scanData: ScanEntry[];
}

function DeviceManagement({ scanData }: DeviceManagementProps) {
  const [devices, setDevices] = useState<Device[]>([]);
  const [beaconId, setBeaconId] = useState('');
  const [name, setName] = useState('');
  const [msg, setMsg] = useState('');

  const loadData = async () => {
    try {
      const data = await getDevices();
      setDevices(data.devices || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Dedupe beacons currently visible on the dashboard (across all anchors), keeping the strongest RSSI seen.
  const detectedBeacons = useMemo(() => {
    const map = new Map<string, DetectedBeacon>();
    for (const entry of scanData || []) {
      for (const b of entry.beacons || []) {
        const existing = map.get(b.beacon_id);
        if (!existing || b.rssi > existing.bestRssi) {
          map.set(b.beacon_id, { beacon_id: b.beacon_id, bestRssi: b.rssi, reportedName: b.name });
        }
      }
    }
    return Array.from(map.values()).sort((a, b) => b.bestRssi - a.bestRssi);
  }, [scanData]);

  const deviceNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const d of devices) map.set(d.beacon_id, d.name);
    return map;
  }, [devices]);

  const handleSelectDetected = (id: string) => {
    setBeaconId(id);
    const existingName = deviceNameMap.get(id);
    const detected = detectedBeacons.find((b) => b.beacon_id === id);
    setName((existingName && existingName !== 'Unknown') ? existingName : (detected?.reportedName || ''));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!beaconId.trim()) return;

    try {
      await createDevice({ beacon_id: beaconId.trim(), name: name.trim() || undefined });
      setMsg('Device berhasil disimpan');
      setBeaconId('');
      setName('');
      loadData();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menyimpan device');
    }
  };

  const handleDelete = async (beaconIdToDelete: string) => {
    if (!confirm('Apakah Anda yakin ingin menghapus log device ini?')) return;
    try {
      await deleteDevice(beaconIdToDelete);
      setMsg('Log device berhasil dihapus');
      loadData();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menghapus device');
    }
  };

  return (
    <div className="panel device-management">
      <h2>Manajemen Device</h2>
      <p className="panel-desc">
        Catat dan beri nama device yang sedang terdeteksi anchor di Dashboard, supaya lebih mudah dikenali
        saat memilihnya di halaman Heatmap.
      </p>
      {msg && <div className="status-banner banner-info">{msg}</div>}

      <div className="layout-split">
        <form onSubmit={handleSubmit} className="form-container" style={{ flex: 1, marginRight: '20px' }}>
          <h3>Log &amp; Beri Nama Device</h3>
          <div className="form-group">
            <label htmlFor="device-detected">Device Terdeteksi Saat Ini</label>
            {detectedBeacons.length > 0 ? (
              <select
                id="device-detected"
                value={beaconId}
                onChange={(e) => handleSelectDetected(e.target.value)}
                required
              >
                <option value="">-- Pilih device yang terdeteksi --</option>
                {detectedBeacons.map((b) => (
                  <option key={b.beacon_id} value={b.beacon_id}>
                    {deviceNameMap.get(b.beacon_id) && deviceNameMap.get(b.beacon_id) !== 'Unknown'
                      ? deviceNameMap.get(b.beacon_id)
                      : b.beacon_id.slice(-8)} ({b.beacon_id}) — {b.bestRssi} dBm
                  </option>
                ))}
              </select>
            ) : (
              <p className="hint">
                Tidak ada device yang terdeteksi saat ini — pastikan minimal satu anchor online di Dashboard.
              </p>
            )}
          </div>
          <div className="form-group">
            <label htmlFor="device-name">Label Device</label>
            <input
              id="device-name"
              type="text"
              placeholder="Contoh: Beacon Ruang Server"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!beaconId}
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={!beaconId}>
              Simpan
            </button>
          </div>
        </form>

        <div className="table-container" style={{ flex: 2 }}>
          <h3>Daftar Device Tercatat</h3>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Beacon ID</th>
                <th>Label</th>
                <th>Tercatat Sejak</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {devices.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center' }}>
                    Belum ada device tercatat
                  </td>
                </tr>
              ) : (
                devices.map((d) => (
                  <tr key={d.beacon_id}>
                    <td className="font-mono">{d.beacon_id}</td>
                    <td><strong>{d.name || '-'}</strong></td>
                    <td>{d.created_at ? new Date(d.created_at).toLocaleString() : '-'}</td>
                    <td>
                      <button className="btn btn-secondary" style={{ padding: '4px 8px', marginRight: '6px' }} onClick={() => handleSelectDetected(d.beacon_id)}>
                        Edit
                      </button>
                      <button className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => handleDelete(d.beacon_id)}>
                        Hapus
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default DeviceManagement;
