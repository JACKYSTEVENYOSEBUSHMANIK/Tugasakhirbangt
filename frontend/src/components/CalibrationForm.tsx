import { useState, useEffect } from 'react';
import { updateAnchors, updateCalibration, getCalibration } from '../services/api';

interface Anchor {
  anchor_id: string;
  x: number;
  y: number;
  label: string;
}

interface CalibrationData {
  calibration: {
    path_loss_exponent: number;
    tx_power_dbm: number;
    min_rssi_threshold: number;
    scan_ttl_seconds: number;
  };
  room: {
    width_m: number;
    height_m: number;
  };
  beacon_filters: string[];
}

interface CalibrationFormProps {
  anchors: Anchor[];
  onAnchorsUpdated: () => void;
}

function CalibrationForm({ anchors, onAnchorsUpdated }: CalibrationFormProps) {
  const [anchorPositions, setAnchorPositions] = useState(
    anchors.map((a) => ({ anchor_id: a.anchor_id, x: a.x, y: a.y }))
  );
  const [calibParams, setCalibParams] = useState({
    path_loss_exponent: 2.0,
    tx_power_dbm: -59,
    min_rssi_threshold: -90,
    scan_ttl_seconds: 15,
  });
  const [roomDimensions, setRoomDimensions] = useState({ width: 10, height: 8 });
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch current calibration params
    const fetchCalib = async () => {
      try {
        const data = await getCalibration();
        if (data && typeof data === 'object' && data.calibration) {
          setCalibParams({
            path_loss_exponent: data.calibration.path_loss_exponent ?? 2.0,
            tx_power_dbm: data.calibration.tx_power_dbm ?? -59,
            min_rssi_threshold: data.calibration.min_rssi_threshold ?? -90,
            scan_ttl_seconds: data.calibration.scan_ttl_seconds ?? 15,
          });
        } else {
          console.error('Invalid calibration data format received:', data);
        }
        if (data && typeof data === 'object' && data.room) {
          setRoomDimensions({
            width: data.room.width_m ?? 10,
            height: data.room.height_m ?? 8,
          });
        }
      } catch (err) {
        console.error('Failed to fetch calibration:', err);
      }
    };
    fetchCalib();
  }, []);

  useEffect(() => {
    setAnchorPositions(
      anchors.map((a) => ({ anchor_id: a.anchor_id, x: a.x, y: a.y }))
    );
  }, [anchors]);

  const handleAnchorChange = (index: number, field: 'x' | 'y', value: string) => {
    const updated = [...anchorPositions];
    updated[index] = { ...updated[index], [field]: parseFloat(value) || 0 };
    setAnchorPositions(updated);
  };

  const handleSaveAnchors = async () => {
    setLoading(true);
    setMessage('');
    try {
      await updateAnchors(anchorPositions);
      setMessage('Anchor positions saved!');
      onAnchorsUpdated();
    } catch (err) {
      setMessage('Failed to save anchor positions');
      console.error(err);
    }
    setLoading(false);
  };

  const handleSaveCalibration = async () => {
    setLoading(true);
    setMessage('');
    try {
      await updateCalibration(calibParams);
      setMessage('Calibration parameters saved! Positions recalculated.');
    } catch (err) {
      setMessage('Failed to save calibration parameters');
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div className="calibration-form">
      <h2>Calibration Settings</h2>

      <div className="calib-section">
        <h3>Room Dimensions</h3>
        <div className="form-row">
          <label>
            Width (m):
            <input
              type="number"
              step="0.5"
              value={roomDimensions.width}
              onChange={(e) =>
                setRoomDimensions({ ...roomDimensions, width: parseFloat(e.target.value) || 0 })
              }
              disabled
            />
          </label>
          <label>
            Height (m):
            <input
              type="number"
              step="0.5"
              value={roomDimensions.height}
              onChange={(e) =>
                setRoomDimensions({ ...roomDimensions, height: parseFloat(e.target.value) || 0 })
              }
              disabled
            />
          </label>
        </div>
        <p className="hint">Room dimensions are set in backend config.json</p>
      </div>

      <div className="calib-section">
        <h3>Anchor Positions</h3>
        <p className="section-desc">
          Measure the physical position of each ESP32 anchor in the room (in meters from origin).
        </p>
        <div className="anchor-inputs">
          {anchorPositions.map((anchor, i) => (
            <div key={anchor.anchor_id} className="anchor-input-row">
              <span className="anchor-label">
                {anchors[i]?.label || anchor.anchor_id}
              </span>
              <label>
                X (m):
                <input
                  type="number"
                  step="0.1"
                  value={anchor.x}
                  onChange={(e) => handleAnchorChange(i, 'x', e.target.value)}
                />
              </label>
              <label>
                Y (m):
                <input
                  type="number"
                  step="0.1"
                  value={anchor.y}
                  onChange={(e) => handleAnchorChange(i, 'y', e.target.value)}
                />
              </label>
            </div>
          ))}
        </div>
        <button onClick={handleSaveAnchors} disabled={loading} className="btn btn-primary">
          Save Anchor Positions
        </button>
      </div>

      <div className="calib-section">
        <h3>Signal Calibration</h3>
        <p className="section-desc">
          Tune these parameters to improve position accuracy.
        </p>

        <div className="form-grid">
          <label>
            Path Loss Exponent (n):
            <input
              type="number"
              step="0.1"
              min="1.5"
              max="5.0"
              value={calibParams.path_loss_exponent}
              onChange={(e) =>
                setCalibParams({
                  ...calibParams,
                  path_loss_exponent: parseFloat(e.target.value) || 2.0,
                })
              }
            />
            <span className="hint">
              Free space: 2.0 | Indoor: 2.7-3.5 | Dense walls: 3.5-5.0
            </span>
          </label>

          <label>
            Reference TX Power (dBm at 1m):
            <input
              type="number"
              step="1"
              value={calibParams.tx_power_dbm}
              onChange={(e) =>
                setCalibParams({
                  ...calibParams,
                  tx_power_dbm: parseInt(e.target.value) || -59,
                })
              }
            />
            <span className="hint">
              Typical BLE beacon: -59 to -65 dBm
            </span>
          </label>

          <label>
            Min RSSI Threshold (dBm):
            <input
              type="number"
              step="1"
              value={calibParams.min_rssi_threshold}
              onChange={(e) =>
                setCalibParams({
                  ...calibParams,
                  min_rssi_threshold: parseInt(e.target.value) || -90,
                })
              }
            />
            <span className="hint">
              Ignore signals weaker than this (default: -90)
            </span>
          </label>

          <label>
            Scan TTL (seconds):
            <input
              type="number"
              step="1"
              min="5"
              max="60"
              value={calibParams.scan_ttl_seconds}
              onChange={(e) =>
                setCalibParams({
                  ...calibParams,
                  scan_ttl_seconds: parseInt(e.target.value) || 15,
                })
              }
            />
            <span className="hint">
              How long scan data is considered fresh
            </span>
          </label>
        </div>

        <button onClick={handleSaveCalibration} disabled={loading} className="btn btn-primary">
          Save Calibration Parameters
        </button>
      </div>

      {message && (
        <div className={`message ${message.includes('Failed') ? 'error' : 'success'}`}>
          {message}
        </div>
      )}

      <div className="calib-section">
        <h3>Calibration Guide</h3>
        <ol className="calib-steps">
          <li>Place the 3 ESP32 anchors at measured positions in the room</li>
          <li>Enter the measured (x, y) coordinates above and save</li>
          <li>Power on all 3 ESP32s and ensure they connect to WiFi</li>
          <li>Place a BLE beacon at a known reference point (e.g., center of room)</li>
          <li>
            Check the Dashboard - if the calculated position doesn't match the
            reference point, adjust the Path Loss Exponent and TX Power
          </li>
          <li>
            Test at 2-3 more reference points to validate accuracy across the room
          </li>
        </ol>
      </div>
    </div>
  );
}

export default CalibrationForm;
