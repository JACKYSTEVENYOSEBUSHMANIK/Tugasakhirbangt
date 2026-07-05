import { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { getLogs } from '../services/api';

interface LogEntry {
  timestamp: number;
  time_str: string;
  level: string;    // INFO, WARN, ERROR, SCAN, HTTP
  source: string;   // ESP, BACKEND, TRILAT, SYSTEM
  message: string;
  data?: unknown;
}

const SOCKET_URL = `http://${window.location.hostname}:5000`;

function Terminal() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<string>('ALL');
  const terminalRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<Socket | null>(null);

  // Load initial logs via REST
  useEffect(() => {
    const loadLogs = async () => {
      try {
        const data = await getLogs(100);
        setLogs(data.logs || []);
      } catch (err) {
        console.error('Failed to load logs:', err);
      }
    };
    loadLogs();
  }, []);

  // Connect to WebSocket for real-time logs
  useEffect(() => {
    const socket: Socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 2000,
    });

    socketRef.current = socket;

    // Receive existing logs on connect
    socket.on('logs_init', (data: { logs: LogEntry[] }) => {
      setLogs(data.logs || []);
    });

    // Receive new log in real-time
    socket.on('log', (entry: LogEntry) => {
      setLogs((prev) => {
        const updated = [...prev, entry];
        // Keep last 200 entries
        if (updated.length > 200) {
          return updated.slice(-200);
        }
        return updated;
      });
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level: string): string => {
    switch (level) {
      case 'SCAN': return '#17a2b8';
      case 'INFO': return '#28a745';
      case 'WARN': return '#ffc107';
      case 'ERROR': return '#dc3545';
      case 'HTTP': return '#6f42c1';
      default: return '#adb5bd';
    }
  };

  const getSourceColor = (source: string): string => {
    switch (source) {
      case 'ESP': return '#007bff';
      case 'BACKEND': return '#6f42c1';
      case 'TRILAT': return '#fd7e14';
      case 'SYSTEM': return '#20c997';
      default: return '#6c757d';
    }
  };

  const filteredLogs = filter === 'ALL'
    ? logs
    : logs.filter((l) => l.source === filter || l.level === filter);

  const handleClear = () => {
    setLogs([]);
  };

  const sourceCounts = logs.reduce((acc, log) => {
    acc[log.source] = (acc[log.source] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="terminal-container">
      <div className="terminal-header">
        <div className="terminal-title">
          <span className="terminal-dot dot-red" />
          <span className="terminal-dot dot-yellow" />
          <span className="terminal-dot dot-green" />
          <span className="terminal-name">Live ESP Positioning Log</span>
        </div>
        <div className="terminal-controls">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="terminal-filter"
          >
            <option value="ALL">All ({logs.length})</option>
            <option value="ESP">ESP ({sourceCounts.ESP || 0})</option>
            <option value="SYSTEM">System ({sourceCounts.SYSTEM || 0})</option>
            <option value="TRILAT">Trilateration ({sourceCounts.TRILAT || 0})</option>
            <option value="SCAN">Scan ({sourceCounts.SCAN || 0})</option>
          </select>
          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
          <button onClick={handleClear} className="terminal-clear-btn">
            Clear
          </button>
        </div>
      </div>

      <div className="terminal-body" ref={terminalRef}>
        {filteredLogs.length === 0 ? (
          <div className="terminal-empty">
            Menunggu data ESP32 dikirim ke /api/scan...
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <div key={i} className="terminal-line">
              <span className="log-time">{log.time_str}</span>
              <span
                className="log-level"
                style={{ color: getLevelColor(log.level) }}
              >
                [{log.level}]
              </span>
              <span
                className="log-source"
                style={{ color: getSourceColor(log.source) }}
              >
                [{log.source}]
              </span>
              <span className="log-message">{log.message}</span>
            </div>
          ))
        )}
      </div>

      <div className="terminal-footer">
        <span className="terminal-stats">
          {filteredLogs.length} entries | Filter: {filter}
        </span>
        <span className="terminal-hint">
          Nyalakan ESP32 dan perhatikan log [SCAN] [ESP]
        </span>
      </div>
    </div>
  );
}

export default Terminal;
