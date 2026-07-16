import { useState, useEffect } from 'react';
import { getHeatmapData, getTrackedDevices } from '../services/api';
import RoomMap, { type HeatPoint, type Zone } from './RoomMap';

interface Anchor {
  anchor_id: string;
  x: number;
  y: number;
  label: string;
  online: boolean;
}

interface Device {
  beacon_id: string;
  name: string;
}

interface HeatmapViewProps {
  roomWidth: number;
  roomHeight: number;
  anchors: Anchor[];
  zones: Zone[];
}

function HeatmapView({ roomWidth, roomHeight, anchors, zones }: HeatmapViewProps) {
  const [beaconId, setBeaconId] = useState('');
  const [deviceList, setDeviceList] = useState<Device[]>([]);
  const [heatmapPoints, setHeatmapPoints] = useState<HeatPoint[]>([]);
  const [maxValue, setMaxValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const [reasonDetail, setReasonDetail] = useState('');

  useEffect(() => {
    getTrackedDevices()
      .then((data) => setDeviceList(data.devices || []))
      .catch((err) => console.error('Failed to fetch tracked device list:', err));
  }, []);

  const handleFetchHeatmap = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!beaconId.trim()) return;

    setLoading(true);
    setMsg('');
    setReasonDetail('');
    try {
      const res = await getHeatmapData(beaconId.trim());
      setHeatmapPoints(res.heatmap || []);
      setMaxValue(res.max_value || 0);
      if ((res.heatmap || []).length === 0) {
        setMsg(
          res.reason === 'no_history'
            ? 'Belum ada data posisi untuk perangkat ini.'
            : res.reason === 'no_stationary_dwell'
              ? 'Data posisi ada, tapi belum terdeteksi waktu diam.'
              : 'Tidak ada data posisi diam terdeteksi untuk perangkat ini.'
        );
        setReasonDetail(res.reason_detail || '');
      }
    } catch (err) {
      console.error(err);
      setMsg('Gagal memuat data heatmap.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel heatmap-view">
      <h2>Peta Durasi Diam / Dwelling Time Heatmap (F6)</h2>

      <form onSubmit={handleFetchHeatmap} className="form-container" style={{ display: 'flex', gap: '15px', alignItems: 'flex-end', marginBottom: '16px', flexWrap: 'wrap' }}>
        {deviceList.length > 0 && (
          <div className="form-group" style={{ minWidth: 220 }}>
            <label htmlFor="heatmap-device" style={{ display: 'block', marginBottom: '6px' }}>Pilih Device</label>
            <select
              id="heatmap-device"
              value={deviceList.some((d) => d.beacon_id === beaconId) ? beaconId : ''}
              onChange={(e) => {
                if (e.target.value) setBeaconId(e.target.value);
              }}
            >
              <option value="">-- Pilih dari device yang punya data posisi --</option>
              {deviceList.map((d) => (
                <option key={d.beacon_id} value={d.beacon_id}>
                  {d.name || d.beacon_id} ({d.beacon_id.slice(-8)})
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="form-group" style={{ flex: 1, minWidth: 220, margin: 0 }}>
          <label htmlFor="heatmap-beacon" style={{ display: 'block', marginBottom: '6px' }}>MAC Address Device</label>
          <input
            id="heatmap-beacon"
            type="text"
            placeholder="Contoh: FF:FF:FF:FF:FF:FF"
            value={beaconId}
            onChange={(e) => setBeaconId(e.target.value)}
            required
            style={{ width: '100%' }}
          />
        </div>
        <button type="submit" className="btn btn-primary" style={{ height: '40px' }} disabled={loading}>
          {loading ? 'Memuat...' : 'Tampilkan Heatmap'}
        </button>
      </form>

      {msg && (
        <div className="status-banner banner-warning">
          {msg}
          {reasonDetail && <div style={{ fontWeight: 400, fontSize: '0.85em', marginTop: 4 }}>{reasonDetail}</div>}
        </div>
      )}

      <div className="heatmap-container" style={{ display: 'flex', gap: '30px', marginTop: '20px', flexWrap: 'wrap' }}>
        <div style={{ flex: '2 1 400px', minWidth: 0, minHeight: 0 }}>
          <RoomMap
            anchors={anchors}
            positions={[]}
            roomWidth={roomWidth}
            roomHeight={roomHeight}
            zones={zones}
            heatPoints={heatmapPoints}
            heatMaxValue={maxValue}
          />
        </div>

        <div className="heatmap-legend" style={{ flex: '1 1 220px', minWidth: '220px' }}>
          <h3>Legend Durasi Diam (Dwelling Time)</h3>
          <p className="hint">
            Dwelling heatmap membedakan titik berdasarkan total durasi (detik) device berhenti/diam di area tertentu, bukan sekadar frekuensi lewat.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', background: 'var(--danger)', borderRadius: '3px', flexShrink: 0 }}></div>
              <span><strong>Durasi Tinggi (&gt; 70%)</strong> — Device diam sangat lama di area ini (contoh: Pantry/Istirahat)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', background: 'var(--warning)', borderRadius: '3px', flexShrink: 0 }}></div>
              <span><strong>Durasi Sedang (40% - 70%)</strong> — Device berhenti sementara (contoh: sinyal melambat)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', background: 'var(--success)', borderRadius: '3px', flexShrink: 0 }}></div>
              <span><strong>Durasi Rendah (&lt; 40%)</strong> — Device berhenti sebentar atau sekadar melintas lambat</span>
            </div>
          </div>

          {maxValue > 0 && (
            <div style={{ marginTop: '25px', padding: '14px', background: 'var(--surface-alt)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.85em' }}>Durasi Maksimum Terdeteksi:</div>
              <div style={{ fontSize: '1.5em', fontWeight: 'bold', color: 'var(--danger)', marginTop: '4px' }}>
                {Math.round(maxValue)} Detik
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default HeatmapView;
