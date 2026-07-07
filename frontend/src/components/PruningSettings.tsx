import { useState, useEffect } from 'react';
import { getPruningConfig, updatePruningConfig, runPruning } from '../services/api';

interface PruningConfig {
  retention_days: number;
  last_pruned_at: string | null;
}

function PruningSettings() {
  const [config, setConfig] = useState<PruningConfig | null>(null);
  const [days, setDays] = useState<number>(30);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');

  const loadConfig = async () => {
    try {
      const res = await getPruningConfig();
      setConfig(res);
      setDays(res.retention_days);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');
    try {
      await updatePruningConfig(days);
      setMsg('Pengaturan pembersihan otomatis berhasil disimpan');
      loadConfig();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menyimpan pengaturan');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerPruning = async () => {
    if (!confirm('Apakah Anda yakin ingin menjalankan pembersihan database sekarang? Tindakan ini akan menghapus log koordinat mentah dan membuat ringkasan agregat.')) return;
    
    setLoading(true);
    setMsg('');
    try {
      const res = await runPruning();
      setMsg(res.message || 'Pembersihan database berhasil diselesaikan.');
      loadConfig();
      setTimeout(() => setMsg(''), 5000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menjalankan pembersihan database.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel pruning-settings">
      <h2>Pembersih Database Otomatis & Pruning (F7)</h2>
      {msg && <div className="status-banner banner-info" style={{ marginBottom: '15px' }}>{msg}</div>}

      <div className="layout-split">
        <form onSubmit={handleSaveConfig} className="form-container" style={{ flex: 1, marginRight: '20px' }}>
          <h3>Konfigurasi Retensi Data</h3>
          <p style={{ color: '#888', fontSize: '0.9em' }}>
            Tentukan berapa lama log sinyal mentah (RSSI & koordinat detik) akan disimpan sebelum dihapus dan digantikan oleh ringkasan harian.
          </p>

          <div className="form-group">
            <label htmlFor="pruning-days">Masa Simpan Data Mentah (Hari)</label>
            <input
              id="pruning-days"
              type="number"
              min="1"
              max="365"
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value) || 30)}
              required
            />
          </div>

          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              Simpan Konfigurasi
            </button>
          </div>
        </form>

        <div style={{ flex: 1, padding: '15px', backgroundColor: '#2c3e50', borderRadius: '8px', border: '1px solid #34495e' }}>
          <h3>Status & Tindakan Manual</h3>
          
          <div style={{ marginBottom: '20px' }}>
            <div style={{ color: '#aaa', fontSize: '0.9em' }}>Terakhir Kali Dijalankan:</div>
            <div style={{ fontSize: '1.2em', fontWeight: 'bold', color: '#2ecc71', marginTop: '4px' }}>
              {config?.last_pruned_at ? new Date(config.last_pruned_at).toLocaleString() : 'Belum pernah dijalankan'}
            </div>
          </div>

          <div style={{ marginBottom: '25px' }}>
            <div style={{ color: '#aaa', fontSize: '0.9em' }}>Mekanisme Otomatis:</div>
            <div style={{ fontSize: '0.95em', marginTop: '4px', color: '#eee' }}>
              Backend menjalankan job otomatis setiap 24 jam untuk membersihkan data yang melewati batas retensi ({config?.retention_days || 30} hari).
            </div>
          </div>

          <div>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ backgroundColor: '#e74c3c', color: 'white', border: 'none', width: '100%', padding: '10px' }}
              onClick={handleTriggerPruning}
              disabled={loading}
            >
              {loading ? 'Memproses...' : 'Jalankan Pembersihan Sekarang (Manual)'}
            </button>
            <small style={{ display: 'block', color: '#aaa', marginTop: '8px', textAlign: 'center' }}>
              Membantu merapikan database secara instan untuk menghemat space NeonDB.
            </small>
          </div>
        </div>
      </div>
    </div>
  );
}

export default PruningSettings;
