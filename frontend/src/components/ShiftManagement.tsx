import { useState, useEffect } from 'react';
import { getShifts, createShift, updateShift, deleteShift } from '../services/api';

interface Shift {
  id_shift: number;
  nama_shift: string;
  jam_mulai: string;
  jam_selesai: string;
}

function ShiftManagement() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [nama, setNama] = useState('');
  const [mulai, setMulai] = useState('08:00');
  const [selesai, setSelesai] = useState('17:00');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [msg, setMsg] = useState('');

  const loadShifts = async () => {
    try {
      const data = await getShifts();
      setShifts(data.shifts || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadShifts();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nama || !mulai || !selesai) return;

    try {
      if (editingId) {
        await updateShift({ id_shift: editingId, nama_shift: nama, jam_mulai: mulai, jam_selesai: selesai });
        setMsg('Shift berhasil diperbarui');
      } else {
        await createShift({ nama_shift: nama, jam_mulai: mulai, jam_selesai: selesai });
        setMsg('Shift berhasil dibuat');
      }
      setNama('');
      setEditingId(null);
      loadShifts();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menyimpan shift');
    }
  };

  const handleEdit = (shift: Shift) => {
    setEditingId(shift.id_shift);
    setNama(shift.nama_shift);
    // Parse time strings like 08:00:00 to 08:00
    setMulai(shift.jam_mulai.slice(0, 5));
    setSelesai(shift.jam_selesai.slice(0, 5));
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Apakah Anda yakin ingin menghapus shift ini?')) return;
    try {
      await deleteShift(id);
      setMsg('Shift berhasil dihapus');
      loadShifts();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menghapus shift');
    }
  };

  return (
    <div className="panel shift-management">
      <h2>Manajemen Shift Kerja</h2>
      {msg && <div className="status-banner banner-info">{msg}</div>}

      <div className="layout-split">
        <form onSubmit={handleSubmit} className="form-container" style={{ flex: 1, marginRight: '20px' }}>
          <h3>{editingId ? 'Edit Shift' : 'Tambah Shift Baru'}</h3>
          <div className="form-group">
            <label htmlFor="shift-nama">Nama Shift</label>
            <input
              id="shift-nama"
              type="text"
              placeholder="Contoh: Pagi, Siang, Malam"
              value={nama}
              onChange={(e) => setNama(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="shift-mulai">Jam Mulai</label>
            <input
              id="shift-mulai"
              type="time"
              value={mulai}
              onChange={(e) => setMulai(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="shift-selesai">Jam Selesai</label>
            <input
              id="shift-selesai"
              type="time"
              value={selesai}
              onChange={(e) => setSelesai(e.target.value)}
              required
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              {editingId ? 'Simpan Perubahan' : 'Tambah Shift'}
            </button>
            {editingId && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingId(null);
                  setNama('');
                }}
              >
                Batal
              </button>
            )}
          </div>
        </form>

        <div className="table-container" style={{ flex: 2 }}>
          <h3>Daftar Shift Kerja Aktif</h3>
          <table className="positions-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nama Shift</th>
                <th>Jam Kerja</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {shifts.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center' }}>
                    Belum ada shift kerja terdaftar
                  </td>
                </tr>
              ) : (
                shifts.map((s) => (
                  <tr key={s.id_shift}>
                    <td>{s.id_shift}</td>
                    <td><strong>{s.nama_shift}</strong></td>
                    <td>{s.jam_mulai.slice(0, 5)} - {s.jam_selesai.slice(0, 5)}</td>
                    <td>
                      <button className="nav-btn active" style={{ padding: '4px 8px', marginRight: '6px' }} onClick={() => handleEdit(s)}>
                        Edit
                      </button>
                      <button className="nav-btn" style={{ padding: '4px 8px', backgroundColor: '#e74c3c', color: 'white' }} onClick={() => handleDelete(s.id_shift)}>
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

export default ShiftManagement;
