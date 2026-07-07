import { useState, useEffect } from 'react';
import { getTasks, createTask, getPetugasList, updateTaskStatus } from '../services/api';

interface Petugas {
  id_petugas: number;
  nama: string;
  beacon_id: string | null;
}

interface Task {
  id_tugas: number;
  id_petugas: number;
  nama_tugas: string;
  target_ruangan: string;
  status_tugas: string;
  waktu_mulai: string | null;
  waktu_selesai: string | null;
  petugas: {
    nama: string;
    beacon_id: string | null;
  };
}

function TaskManagement() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [petugasList, setPetugasList] = useState<Petugas[]>([]);
  const [taskName, setTaskName] = useState('');
  const [petugasId, setPetugasId] = useState('');
  const [targetRoom, setTargetRoom] = useState('Ruang VIP');
  const [msg, setMsg] = useState('');

  const loadData = async () => {
    try {
      const dataTasks = await getTasks();
      const dataPetugas = await getPetugasList();
      setTasks(dataTasks.tasks || []);
      setPetugasList(dataPetugas.petugas || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
    // Poll for status updates every 3 seconds
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskName || !petugasId || !targetRoom) return;

    try {
      await createTask({
        id_petugas: parseInt(petugasId),
        nama_tugas: taskName,
        target_ruangan: targetRoom,
      });
      setTaskName('');
      setPetugasId('');
      setMsg('Penugasan berhasil dibuat');
      loadData();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal membuat penugasan');
    }
  };

  const handleUpdateStatus = async (id: number, status: string) => {
    try {
      await updateTaskStatus(id, status);
      setMsg('Status penugasan diperbarui');
      loadData();
      setTimeout(() => setMsg(''), 2000);
    } catch (err) {
      console.error(err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Completed':
        return '#2ecc71'; // Green
      case 'On Progress':
        return '#f1c40f'; // Yellow
      default:
        return '#e67e22'; // Orange/Pending
    }
  };

  return (
    <div className="panel task-management">
      <h2>Sistem Penugasan & Pelacakan Lokasi (F5)</h2>
      {msg && <div className="status-banner banner-info">{msg}</div>}

      <div className="layout-split">
        <form onSubmit={handleSubmit} className="form-container" style={{ flex: 1, marginRight: '20px' }}>
          <h3>Buat Tugas Baru</h3>
          <div className="form-group">
            <label htmlFor="task-name">Nama Tugas</label>
            <input
              id="task-name"
              type="text"
              placeholder="Contoh: Cek Kunci Pintu VIP, Patroli Pantry"
              value={taskName}
              onChange={(e) => setTaskName(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="task-petugas">Petugas Penerima</label>
            <select id="task-petugas" value={petugasId} onChange={(e) => setPetugasId(e.target.value)} required>
              <option value="">-- Pilih Petugas --</option>
              {petugasList.map((p) => (
                <option key={p.id_petugas} value={p.id_petugas}>
                  {p.nama} ({p.beacon_id ? p.beacon_id.slice(-8) : 'No Beacon'})
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="task-room">Target Ruangan</label>
            <select id="task-room" value={targetRoom} onChange={(e) => setTargetRoom(e.target.value)} required>
              <option value="Ruang VIP">Ruang VIP</option>
              <option value="Pantry">Pantry</option>
              <option value="Lobi">Lobi</option>
            </select>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              Kirim Penugasan
            </button>
          </div>
        </form>

        <div className="table-container" style={{ flex: 2 }}>
          <h3>Daftar Tugas & Status Deteksi Real-Time</h3>
          <table className="positions-table">
            <thead>
              <tr>
                <th>Tugas</th>
                <th>Petugas</th>
                <th>Target</th>
                <th>Status</th>
                <th>Waktu Deteksi</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {tasks.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center' }}>
                    Belum ada penugasan terdaftar
                  </td>
                </tr>
              ) : (
                tasks.map((t) => (
                  <tr key={t.id_tugas}>
                    <td>
                      <strong>{t.nama_tugas}</strong>
                    </td>
                    <td>{t.petugas ? t.petugas.nama : 'Unknown'}</td>
                    <td><span className="badge badge-info">{t.target_ruangan}</span></td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          backgroundColor: getStatusColor(t.status_tugas),
                          color: 'white',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          fontWeight: 'bold',
                        }}
                      >
                        {t.status_tugas}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.85em', color: '#888' }}>
                      {t.waktu_mulai && (
                        <div>
                          Mulai: {new Date(t.waktu_mulai).toLocaleTimeString()}
                        </div>
                      )}
                      {t.waktu_selesai && (
                        <div>
                          Selesai: {new Date(t.waktu_selesai).toLocaleTimeString()}
                        </div>
                      )}
                      {!t.waktu_mulai && 'Menunggu kehadiran...'}
                    </td>
                    <td>
                      {t.status_tugas !== 'Completed' && (
                        <button
                          className="nav-btn active"
                          style={{ padding: '4px 8px', fontSize: '0.85em' }}
                          onClick={() => handleUpdateStatus(t.id_tugas, 'Completed')}
                        >
                          Selesaikan
                        </button>
                      )}
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

export default TaskManagement;
