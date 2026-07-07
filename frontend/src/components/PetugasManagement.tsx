import { useState, useEffect } from 'react';
import { getPetugasList, createPetugas, updatePetugas, deletePetugas, getShifts } from '../services/api';

interface Shift {
  id_shift: number;
  nama_shift: string;
}

interface Petugas {
  id_petugas: number;
  nama: string;
  beacon_id: string | null;
  id_shift: number | null;
  shift_kerja: {
    nama_shift: string;
    jam_mulai: string;
    jam_selesai: string;
  } | null;
}

function PetugasManagement() {
  const [petugasList, setPetugasList] = useState<Petugas[]>([]);
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [nama, setNama] = useState('');
  const [beaconId, setBeaconId] = useState('');
  const [shiftId, setShiftId] = useState<string>('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [msg, setMsg] = useState('');

  const loadData = async () => {
    try {
      const dataPetugas = await getPetugasList();
      const dataShifts = await getShifts();
      setPetugasList(dataPetugas.petugas || []);
      setShifts(dataShifts.shifts || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nama) return;

    const bId = beaconId.trim() ? beaconId.trim() : null;
    const sId = shiftId ? parseInt(shiftId) : null;

    try {
      if (editingId) {
        await updatePetugas({ id_petugas: editingId, nama, beacon_id: bId, id_shift: sId });
        setMsg('Petugas berhasil diperbarui');
      } else {
        await createPetugas({ nama, beacon_id: bId, id_shift: sId });
        setMsg('Petugas berhasil didaftarkan');
      }
      setNama('');
      setBeaconId('');
      setShiftId('');
      setEditingId(null);
      loadData();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menyimpan petugas');
    }
  };

  const handleEdit = (p: Petugas) => {
    setEditingId(p.id_petugas);
    setNama(p.nama);
    setBeaconId(p.beacon_id || '');
    setShiftId(p.id_shift ? p.id_shift.toString() : '');
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Apakah Anda yakin ingin menghapus petugas ini?')) return;
    try {
      await deletePetugas(id);
      setMsg('Petugas berhasil dihapus');
      loadData();
      setTimeout(() => setMsg(''), 3000);
    } catch (err) {
      console.error(err);
      setMsg('Gagal menghapus petugas');
    }
  };

  return (
    <div className="panel petugas-management">
      <h2>Manajemen Petugas & Beacon</h2>
      {msg && <div className="status-banner banner-info">{msg}</div>}

      <div className="layout-split">
        <form onSubmit={handleSubmit} className="form-container" style={{ flex: 1, marginRight: '20px' }}>
          <h3>{editingId ? 'Edit Petugas' : 'Daftarkan Petugas Baru'}</h3>
          <div className="form-group">
            <label htmlFor="petugas-nama">Nama Lengkap</label>
            <input
              id="petugas-nama"
              type="text"
              placeholder="Nama Petugas"
              value={nama}
              onChange={(e) => setNama(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="petugas-beacon">Beacon MAC Address</label>
            <input
              id="petugas-beacon"
              type="text"
              placeholder="Contoh: AA:BB:CC:DD:EE:FF"
              value={beaconId}
              onChange={(e) => setBeaconId(e.target.value)}
            />
            <small style={{ color: '#aaa' }}>Format standard MAC 6-Byte hex, pisahkan dengan titik dua</small>
          </div>
          <div className="form-group">
            <label htmlFor="petugas-shift">Shift Kerja</label>
            <select id="petugas-shift" value={shiftId} onChange={(e) => setShiftId(e.target.value)}>
              <option value="">-- Pilih Shift Kerja --</option>
              {shifts.map((s) => (
                <option key={s.id_shift} value={s.id_shift}>
                  {s.nama_shift}
                </option>
              ))}
            </select>
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary">
              {editingId ? 'Simpan Perubahan' : 'Daftarkan'}
            </button>
            {editingId && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  setEditingId(null);
                  setNama('');
                  setBeaconId('');
                  setShiftId('');
                }}
              >
                Batal
              </button>
            )}
          </div>
        </form>

        <div className="table-container" style={{ flex: 2 }}>
          <h3>Daftar Petugas Terdaftar</h3>
          <table className="positions-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nama</th>
                <th>Beacon ID</th>
                <th>Shift Kerja</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {petugasList.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center' }}>
                    Belum ada petugas terdaftar
                  </td>
                </tr>
              ) : (
                petugasList.map((p) => (
                  <tr key={p.id_petugas}>
                    <td>{p.id_petugas}</td>
                    <td><strong>{p.nama}</strong></td>
                    <td style={{ fontFamily: 'monospace' }}>{p.beacon_id || 'Belum di-assign'}</td>
                    <td>
                      {p.shift_kerja ? (
                        <span className="badge badge-info" style={{ backgroundColor: '#2ecc71', color: 'white', padding: '2px 6px', borderRadius: '4px' }}>
                          {p.shift_kerja.nama_shift} ({p.shift_kerja.jam_mulai.slice(0, 5)} - {p.shift_kerja.jam_selesai.slice(0, 5)})
                        </span>
                      ) : (
                        <span style={{ color: '#aaa' }}>Belum di-assign</span>
                      )}
                    </td>
                    <td>
                      <button className="nav-btn active" style={{ padding: '4px 8px', marginRight: '6px' }} onClick={() => handleEdit(p)}>
                        Edit
                      </button>
                      <button className="nav-btn" style={{ padding: '4px 8px', backgroundColor: '#e74c3c', color: 'white' }} onClick={() => handleDelete(p.id_petugas)}>
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

export default PetugasManagement;
