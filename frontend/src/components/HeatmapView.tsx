import { useState, useEffect, useRef } from 'react';
import { getHeatmapData } from '../services/api';

interface HeatPoint {
  x: number;
  y: number;
  value: number;
}

interface HeatmapViewProps {
  roomWidth: number;
  roomHeight: number;
}

function HeatmapView({ roomWidth, roomHeight }: HeatmapViewProps) {
  const [beaconId, setBeaconId] = useState('');
  const [heatmapPoints, setHeatmapPoints] = useState<HeatPoint[]>([]);
  const [maxValue, setMaxValue] = useState(0);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const handleFetchHeatmap = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!beaconId.trim()) return;

    setLoading(true);
    setMsg('');
    try {
      const res = await getHeatmapData(beaconId.trim());
      setHeatmapPoints(res.heatmap || []);
      setMaxValue(res.max_value || 0);
      if ((res.heatmap || []).length === 0) {
        setMsg('Tidak ada data posisi diam terdeteksi untuk perangkat ini.');
      }
    } catch (err) {
      console.error(err);
      setMsg('Gagal memuat data heatmap.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    drawHeatmap();
  }, [heatmapPoints, maxValue]);

  const drawHeatmap = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw room grid lines
    ctx.strokeStyle = '#2c3e50';
    ctx.lineWidth = 1;
    const gridSpacing = 40; // Pixels representing 1 meter
    
    // Draw vertical grid lines
    for (let x = 0; x <= canvas.width; x += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    // Draw horizontal grid lines
    for (let y = 0; y <= canvas.height; y += gridSpacing) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Draw Heatmap color blobs
    if (heatmapPoints.length === 0 || maxValue === 0) return;

    // Convert coordinates to canvas pixels
    // mapping coordinates: room dimensions match width/height
    const scaleX = canvas.width / roomWidth;
    const scaleY = canvas.height / roomHeight;

    heatmapPoints.forEach((p) => {
      // Invert Y coordinate since canvas Y goes down and room Y goes up (standard Cartesian)
      const cx = p.x * scaleX;
      const cy = canvas.height - (p.y * scaleY);
      
      const intensity = p.value / maxValue; // 0.0 to 1.0

      // Draw radial gradient color blob representing dwelling duration
      const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, 30);
      
      // Color scale: Red (High) -> Orange -> Yellow -> Green -> Alpha (None)
      let colorStr = 'rgba(46, 204, 113, 0.4)'; // Default Green
      if (intensity > 0.7) {
        colorStr = `rgba(231, 76, 60, ${intensity * 0.8})`; // Red
      } else if (intensity > 0.4) {
        colorStr = `rgba(241, 196, 15, ${intensity * 0.7})`; // Yellow
      } else {
        colorStr = `rgba(46, 204, 113, ${intensity * 0.6})`; // Green
      }

      grad.addColorStop(0, colorStr);
      grad.addColorStop(1, 'rgba(0,0,0,0)');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, 30, 0, 2 * Math.PI);
      ctx.fill();
    });

    // Label coordinates on grid
    ctx.fillStyle = '#7f8c8d';
    ctx.font = '10px sans-serif';
    for (let x = 0; x <= roomWidth; x++) {
      ctx.fillText(`${x}m`, x * scaleX + 5, canvas.height - 5);
    }
    for (let y = 0; y <= roomHeight; y++) {
      ctx.fillText(`${y}m`, 5, canvas.height - (y * scaleY) - 5);
    }
  };

  return (
    <div className="panel heatmap-view">
      <h2>Peta Durasi Diam / Dwelling Time Heatmap (F6)</h2>
      
      <form onSubmit={handleFetchHeatmap} className="form-container" style={{ display: 'flex', gap: '15px', alignItems: 'flex-end', marginBottom: '20px' }}>
        <div className="form-group" style={{ flex: 1, margin: 0 }}>
          <label htmlFor="heatmap-beacon" style={{ display: 'block', marginBottom: '6px' }}>MAC Address Beacon Petugas</label>
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

      {msg && <div className="status-banner banner-warning">{msg}</div>}

      <div className="heatmap-container" style={{ display: 'flex', gap: '30px', marginTop: '20px', flexWrap: 'wrap' }}>
        <div style={{ backgroundColor: '#1a1a1a', borderRadius: '8px', padding: '15px', border: '2px solid #2c3e50' }}>
          <canvas
            ref={canvasRef}
            width={400}
            height={320}
            style={{ display: 'block', backgroundColor: '#000000' }}
          />
        </div>

        <div className="heatmap-legend" style={{ flex: 1, minWidth: '220px' }}>
          <h3>Legend Durasi Diam (Dwelling Time)</h3>
          <p style={{ color: '#888', fontSize: '0.9em' }}>
            Dwelling heatmap membedakan titik berdasarkan total durasi (detik) petugas berhenti/diam di area tertentu, bukan sekadar frekuensi lewat.
          </p>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', backgroundColor: '#e74c3c', borderRadius: '3px' }}></div>
              <span><strong>Durasi Tinggi (Stationary &gt; 70%)</strong> - Petugas diam sangat lama di area ini (contoh: Pantry/Istirahat)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', backgroundColor: '#f1c40f', borderRadius: '3px' }}></div>
              <span><strong>Durasi Sedang (Stationary 40% - 70%)</strong> - Petugas berhenti sementara (contoh: Melakukan cek tugas)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <div style={{ width: '30px', height: '15px', backgroundColor: '#2ecc71', borderRadius: '3px' }}></div>
              <span><strong>Durasi Rendah (Stationary &lt; 40%)</strong> - Petugas berhenti sebentar atau sekadar melintas lambat</span>
            </div>
          </div>

          {maxValue > 0 && (
            <div style={{ marginTop: '25px', padding: '12px', backgroundColor: '#2c3e50', borderRadius: '6px' }}>
              <div><strong>Durasi Maksimum Terdeteksi:</strong></div>
              <div style={{ fontSize: '1.5em', fontWeight: 'bold', color: '#e74c3c', marginTop: '4px' }}>
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
