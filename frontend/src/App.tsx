import { useState, useEffect, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import RoomMap from './components/RoomMap';
import AnchorPanel from './components/AnchorPanel';
import CalibrationForm from './components/CalibrationForm';
import Terminal from './components/Terminal';
import {
  getAnchors,
  getPositions,
  getScanData,
  getFullConfig,
  getHealth,
} from './services/api';

interface Anchor {
  anchor_id: string;
  x: number;
  y: number;
  label: string;
  online: boolean;
  last_seen: number | null;
  beacons_detected: number;
}

interface Position {
  beacon_id: string;
  position: [number, number] | null;
  error: number | null;
  anchors_used: number;
  method: string;
  anchor_details?: Array<{
    anchor_id: string;
    rssi: number;
    tx_power: number;
    estimated_distance_m: number;
  }>;
}

interface ScanEntry {
  anchor_id: string;
  anchor_pos: [number, number];
  timestamp: number;
  calibration_mode: boolean;
  beacons: Array<{
    beacon_id: string;
    rssi: number;
    tx_power: number;
    name?: string;
  }>;
  age_seconds: number;
}

type Page = 'dashboard' | 'calibration';

const SOCKET_URL = `http://${window.location.hostname}:5000`;

function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [anchors, setAnchors] = useState<Anchor[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [scanData, setScanData] = useState<ScanEntry[]>([]);
  const [roomDims, setRoomDims] = useState({ width: 10, height: 8 });
  const [health, setHealth] = useState<{ status: string; anchors_reporting: number; anchors_total: number; beacons_tracked: number; system_ready: boolean } | null>(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);

  // Fetch data functions
  const fetchAnchors = useCallback(async () => {
    try {
      const data = await getAnchors();
      setAnchors(data.anchors || []);
    } catch (err) {
      console.error('Failed to fetch anchors:', err);
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    try {
      const data = await getPositions();
      setPositions(data.positions || []);
    } catch (err) {
      console.error('Failed to fetch positions:', err);
    }
  }, []);

  const fetchScanData = useCallback(async () => {
    try {
      const data = await getScanData();
      setScanData(data.scan_data || []);
    } catch (err) {
      console.error('Failed to fetch scan data:', err);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const config = await getFullConfig();
      if (config.room) {
        setRoomDims({
          width: config.room.width_m,
          height: config.room.height_m,
        });
      }
    } catch (err) {
      console.error('Failed to fetch config:', err);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getHealth();
      setHealth(data);
      setBackendOnline(true);
    } catch (err) {
      setBackendOnline(false);
      setHealth(null);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    fetchAnchors();
    fetchPositions();
    fetchScanData();
    fetchConfig();
    fetchHealth();
  }, [fetchAnchors, fetchPositions, fetchScanData, fetchConfig, fetchHealth]);

  // Periodic polling (fallback if WebSocket not connected)
  useEffect(() => {
    const interval = setInterval(() => {
      if (!socketConnected) {
        fetchPositions();
        fetchScanData();
        fetchAnchors();
        fetchHealth();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [socketConnected, fetchPositions, fetchScanData, fetchAnchors, fetchHealth]);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const socket: Socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 2000,
    });

    socket.on('connect', () => {
      setSocketConnected(true);
      console.log('WebSocket connected');
    });

    socket.on('disconnect', () => {
      setSocketConnected(false);
      console.log('WebSocket disconnected');
    });

    socket.on('positions_update', (data: { positions: Position[] }) => {
      setPositions(data.positions || []);
      // Also refresh anchors and scan data
      fetchAnchors();
      fetchScanData();
      fetchHealth();
    });

    socket.on('error', (err: { message: string }) => {
      console.error('WebSocket error:', err.message);
    });

    return () => {
      socket.disconnect();
    };
  }, [fetchAnchors, fetchScanData, fetchHealth]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>BLE Room Positioning System</h1>
        <nav className="nav-tabs">
          <button
            className={`nav-btn ${page === 'dashboard' ? 'active' : ''}`}
            onClick={() => setPage('dashboard')}
          >
            Dashboard
          </button>
          <button
            className={`nav-btn ${page === 'calibration' ? 'active' : ''}`}
            onClick={() => setPage('calibration')}
          >
            Calibration
          </button>
        </nav>
        <div className="header-status">
          <span className={`conn-indicator ${backendOnline && socketConnected ? 'connected' : 'disconnected'}`}>
            {!backendOnline ? 'Backend Offline' : socketConnected ? 'Connected' : 'Polling...'}
          </span>
          {health && (
            <span className="health-info">
              {health.anchors_reporting}/{health.anchors_total} anchors | {health.beacons_tracked} beacons
            </span>
          )}
        </div>
      </header>

      {/* System status banners */}
      {!backendOnline && (
        <div className="status-banner banner-error">
          Backend server is not reachable. Make sure it's running on port 5000.
        </div>
      )}
      {backendOnline && health && !health.system_ready && (
        <div className="status-banner banner-warning">
          Waiting for anchors: {health.anchors_reporting}/3 online. Positions will appear once all 3 anchors are reporting data.
        </div>
      )}
      {backendOnline && health && health.system_ready && positions.length === 0 && (
        <div className="status-banner banner-info">
          All anchors connected. Waiting for BLE beacon detections...
        </div>
      )}

      <main className="app-main">
        {page === 'dashboard' && (
          <div className="dashboard-page">
            <div className="dashboard">
              <div className="dashboard-map">
                <RoomMap
                  anchors={anchors}
                  positions={health?.system_ready ? positions : []}
                  roomWidth={roomDims.width}
                  roomHeight={roomDims.height}
                />
              </div>
              <div className="dashboard-panel">
                <AnchorPanel anchors={anchors} scanData={scanData} />

                {health?.system_ready && positions.length > 0 && (
                  <div className="positions-summary">
                    <h2>Tracked Beacons</h2>
                    <table className="positions-table">
                      <thead>
                        <tr>
                          <th>Beacon</th>
                          <th>Position (x, y)</th>
                          <th>Error</th>
                          <th>Anchors</th>
                        </tr>
                      </thead>
                      <tbody>
                        {positions.map((pos) => (
                          <tr key={pos.beacon_id}>
                            <td title={pos.beacon_id}>
                              {pos.beacon_id.slice(-8)}
                            </td>
                            <td>
                              {pos.position
                                ? `(${pos.position[0]}, ${pos.position[1]})`
                                : 'N/A'}
                            </td>
                            <td>
                              {pos.error !== null
                                ? `${pos.error.toFixed(2)} m`
                                : 'N/A'}
                            </td>
                            <td>{pos.anchors_used}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <section className="positioning-log" aria-label="ESP positioning data log">
              <Terminal />
            </section>
          </div>
        )}

        {page === 'calibration' && (
          <div className="calibration-page">
            <CalibrationForm
              anchors={anchors}
              onAnchorsUpdated={() => {
                fetchAnchors();
                fetchConfig();
              }}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
