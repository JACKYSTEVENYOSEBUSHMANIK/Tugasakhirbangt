import { useState, useEffect } from 'react';
import { calibrateNode, getCalibrationHistory, getLogs } from '../services/api';

interface Anchor {
  anchor_id: string;
  label: string;
  online: boolean;
  beacons_detected: number;
}

interface CalibHistory {
  log_id: number;
  anchor_id: string;
  p_tx_old: number;
  p_tx_new: number;
  faktor_n_old: number;
  faktor_n_new: number;
  calibrated_at: string;
}

interface LogEntry {
  timestamp: number;
  time_str: string;
  level: string;
  source: string;
  message: string;
}

interface SignalMonitorProps {
  anchors: Anchor[];
}

function SignalMonitor({ anchors }: SignalMonitorProps) {
  const [beaconId, setBeaconId] = useState('');
  const [history, setHistory] = useState<CalibHistory[]>([]);
  const [warnings, setWarnings] = useState<LogEntry[]>([]);
  const [msg, setMsg] = useState('');
  const [loadingAnchor, setLoadingAnchor] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const dataHist = await getCalibrationHistory();
      setHistory(dataHist.history || []);
      
      const dataLogs = await getLogs(50);
      const warnLogs = (dataLogs.logs || []).filter((l: LogEntry) => l.level === 'WARN');
      setWarnings(warnLogs);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleCalibrate = async (anchorId: string) => {
    setLoadingAnchor(anchorId);
    setMsg('');
    try {
      const res = await calibrateNode(anchorId, beaconId.trim() ? beaconId.trim() : undefined);
      setMsg(`Sukses! Node ${res.anchor_id} berhasil dikalibrasi. Nilai P_tx diperbarui menjadi ${res.p_tx} dBm.`);
      loadData();
    } catch (err: any) {
      console.error(err);
      setMsg(`Kesalahan kalibrasi: ${err.response?.data?.error || err.message}`);
    } finally {
      setLoadingAnchor(null);
    }
  };

  return (
    <div className="panel signal-monitor">
      <h2>Pemantauan Sinyal & Notifikasi (F2) & Kalibrator (F1)</h2>
      {msg && <div className="status-banner banner-info" style={{ marginBottom: '15px' }}>{msg}</div>}

      <div className="form-group" style={{ maxWidth: '400px', marginBottom: '20px' }}>
        <label htmlFor="calib-beacon">MAC Address Beacon Kalibrasi (Opsional)</label>
        <input
          id="calib-beacon"
          type="text"
          placeholder="Format: AA:BB:CC:DD:EE:FF (Kosong = Otomatis terkuat)"
          value={beaconId}
          onChange={(e) => setBeaconId(e.target.value)}
        />
        <small style={{ color: '#aaa' }}>Membantu mengunci beacon tertentu yang berada tepat 1 meter dari node.</small>
      </div>

      <div className="layout-split">
        <div style={{ flex: 1, marginRight: '20px' }}>
          <h3>Daftar Node & Tombol Kalibrasi Cepat</h3>
          <div className="anchors-list-calib">
            {anchors.map((a) => (
              <div key={a.anchor_id} className="anchor-item" style={{
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '10px',
                padding: '14px 18px',
                marginBottom: '12px',
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                transition: 'all 0.3s'
              }}>
                <div>
                  <h4 style={{ margin: '0 0 4px 0' }}>{a.label} ({a.anchor_id})</h4>
                  <span style={{ fontSize: '0.85em', color: a.online ? '#2ecc71' : '#e74c3c' }}>
                    ● {a.online ? 'Online' : 'Offline'}
                  </span>
                  <span style={{ fontSize: '0.85em', color: '#aaa', marginLeft: '12px' }}>
                    Beacon terdeteksi: {a.beacons_detected}
                  </span>
                </div>
                <button
                  className="btn btn-primary"
                  style={{ padding: '6px 12px', fontSize: '0.9em' }}
                  onClick={() => handleCalibrate(a.anchor_id)}
                  disabled={loadingAnchor !== null}
                >
                  {loadingAnchor === a.anchor_id ? 'Mengukur...' : 'Kalibrasi 1 Meter'}
                </button>
              </div>
            ))}
          </div>

          <h3 style={{ marginTop: '20px' }}>Notifikasi Gangguan Sinyal & Anomali (F2)</h3>
          <div className="warnings-list" style={{
            maxHeight: '220px',
            overflowY: 'auto',
            backgroundColor: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            borderRadius: '10px',
            padding: '12px'
          }}>
            {warnings.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', textAlign: 'center', margin: '20px 0', fontSize: '0.9em' }}>
                Tidak ada gangguan atau anomali sinyal terdeteksi saat ini.
              </p>
            ) : (
              warnings.map((w, index) => (
                <div key={index} style={{
                  borderLeft: '4px solid var(--warning)',
                  padding: '10px',
                  marginBottom: '10px',
                  backgroundColor: 'rgba(251, 191, 36, 0.05)',
                  borderRadius: '0 8px 8px 0',
                  border: '1px solid rgba(251, 191, 36, 0.1)',
                  borderLeftWidth: '4px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8em', color: '#e67e22', marginBottom: '4px' }}>
                    <span><strong>{w.source} WARNING</strong></span>
                    <span>{w.time_str}</span>
                  </div>
                  <div style={{ fontSize: '0.9em', color: '#f39c12' }}>{w.message}</div>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <h3>Riwayat Kalibrasi Node</h3>
          <table className="positions-table" style={{ fontSize: '0.9em' }}>
            <thead>
              <tr>
                <th>Node</th>
                <th>P_tx Lama</th>
                <th>P_tx Baru</th>
                <th>Waktu</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center' }}>
                    Belum ada riwayat kalibrasi terdaftar
                  </td>
                </tr>
              ) : (
                history.map((h) => (
                  <tr key={h.log_id}>
                    <td><strong>{h.anchor_id}</strong></td>
                    <td style={{ color: '#e74c3c' }}>{h.p_tx_old} dBm</td>
                    <td style={{ color: '#2ecc71', fontWeight: 'bold' }}>{h.p_tx_new} dBm</td>
                    <td style={{ fontSize: '0.85em', color: '#aaa' }}>
                      {new Date(h.calibrated_at).toLocaleString()}
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

export default SignalMonitor;
