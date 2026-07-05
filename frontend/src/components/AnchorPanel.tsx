interface Anchor {
  anchor_id: string;
  x: number;
  y: number;
  label: string;
  online: boolean;
  last_seen: number | null;
  beacons_detected: number;
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

interface AnchorPanelProps {
  anchors: Anchor[];
  scanData: ScanEntry[];
}

function AnchorPanel({ anchors, scanData }: AnchorPanelProps) {
  const getScanForAnchor = (anchorId: string) => {
    return scanData.find((s) => s.anchor_id === anchorId);
  };

  const formatLastSeen = (lastSeen: number | null) => {
    if (!lastSeen) return 'Never';
    const ago = Math.floor((Date.now() - lastSeen) / 1000);
    if (ago < 60) return `${ago}s ago`;
    if (ago < 3600) return `${Math.floor(ago / 60)}m ago`;
    return `${Math.floor(ago / 3600)}h ago`;
  };

  const getConnectionStage = (anchor: Anchor, scan: ScanEntry | undefined): {
    stage: number;       // 0=offline, 1=wifi, 2=backend, 3=active
    label: string;
    color: string;
  } => {
    if (!anchor.online && !scan) {
      return { stage: 0, label: 'Offline - Not reporting', color: '#dc3545' };
    }
    if (!scan) {
      return { stage: 1, label: 'WiFi connected, no data yet', color: '#ffc107' };
    }
    if (scan.age_seconds > 20) {
      return { stage: 1, label: 'Data stale - ESP may be disconnected', color: '#ffc107' };
    }
    if (scan.beacons.length === 0) {
      return { stage: 2, label: 'Connected to backend, no beacons seen', color: '#17a2b8' };
    }
    return { stage: 3, label: 'Active - Sending data to backend', color: '#28a745' };
  };

  return (
    <div className="anchor-panel">
      <h2>Anchor Status</h2>
      <p className="panel-desc">Shows connection from each ESP32 to the backend server</p>
      <div className="anchor-grid">
        {anchors.map((anchor) => {
          const scan = getScanForAnchor(anchor.anchor_id);
          const conn = getConnectionStage(anchor, scan);

          return (
            <div
              key={anchor.anchor_id}
              className={`anchor-card ${anchor.online ? 'online' : 'offline'}`}
            >
              {/* Connection status header */}
              <div className="anchor-header">
                <span
                  className="status-dot"
                  style={{ background: conn.color, boxShadow: `0 0 6px ${conn.color}` }}
                />
                <h3>{anchor.label || anchor.anchor_id}</h3>
                <span className={`conn-stage-badge`} style={{ background: conn.color }}>
                  {conn.stage === 0 && 'OFFLINE'}
                  {conn.stage === 1 && 'WAITING'}
                  {conn.stage === 2 && 'NO BEACONS'}
                  {conn.stage === 3 && 'ACTIVE'}
                </span>
              </div>

              {/* Data flow visualization */}
              <div className="data-flow">
                <div className={`flow-step ${conn.stage >= 1 ? 'flow-active' : 'flow-inactive'}`}>
                  <span className="flow-icon">ESP</span>
                  <span className="flow-label">{anchor.anchor_id}</span>
                </div>
                <div className={`flow-arrow ${conn.stage >= 1 ? 'flow-active' : 'flow-inactive'}`}>
                  --WiFi--&gt;
                </div>
                <div className={`flow-step ${conn.stage >= 2 ? 'flow-active' : 'flow-inactive'}`}>
                  <span className="flow-icon">NET</span>
                  <span className="flow-label">HTTP POST</span>
                </div>
                <div className={`flow-arrow ${conn.stage >= 3 ? 'flow-active' : 'flow-inactive'}`}>
                  --data--&gt;
                </div>
                <div className={`flow-step ${conn.stage >= 3 ? 'flow-active' : 'flow-inactive'}`}>
                  <span className="flow-icon">API</span>
                  <span className="flow-label">Backend</span>
                </div>
              </div>

              <p className="conn-label" style={{ color: conn.color }}>
                {conn.label}
              </p>

              {/* Details */}
              <div className="anchor-info">
                <div className="info-row">
                  <span className="info-label">ID:</span>
                  <span className="info-value">{anchor.anchor_id}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Position:</span>
                  <span className="info-value">
                    ({anchor.x}, {anchor.y}) m
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-label">Last seen:</span>
                  <span className="info-value">
                    {formatLastSeen(anchor.last_seen)}
                  </span>
                </div>
                {scan && (
                  <div className="info-row">
                    <span className="info-label">Data age:</span>
                    <span className={`info-value ${scan.age_seconds > 15 ? 'text-warning' : 'text-online'}`}>
                      {scan.age_seconds}s {scan.age_seconds > 15 ? '(stale!)' : '(fresh)'}
                    </span>
                  </div>
                )}
                <div className="info-row">
                  <span className="info-label">Beacons detected:</span>
                  <span className="info-value">{anchor.beacons_detected}</span>
                </div>
              </div>

              {/* Beacon list */}
              {scan && scan.beacons.length > 0 && (
                <div className="anchor-beacons">
                  <h4>Detected Beacons</h4>
                  <table className="beacon-table">
                    <thead>
                      <tr>
                        <th>Beacon</th>
                        <th>RSSI</th>
                        <th>TX</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scan.beacons.slice(0, 5).map((b) => (
                        <tr key={b.beacon_id}>
                          <td className="beacon-id" title={b.beacon_id}>
                            {b.name || b.beacon_id.slice(-8)}
                          </td>
                          <td className={`rssi-${getRssiLevel(b.rssi)}`}>
                            {b.rssi}
                          </td>
                          <td>{b.tx_power}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {scan.beacons.length > 5 && (
                    <p className="more-beacons">
                      +{scan.beacons.length - 5} more...
                    </p>
                  )}
                </div>
              )}

              {scan?.calibration_mode && (
                <div className="calib-badge">CALIBRATION MODE</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function getRssiLevel(rssi: number): string {
  if (rssi >= -50) return 'strong';
  if (rssi >= -70) return 'medium';
  return 'weak';
}

export default AnchorPanel;
