import { useEffect, useRef } from 'react';

interface Anchor {
  anchor_id: string;
  x: number;
  y: number;
  label: string;
  online: boolean;
}

interface Position {
  beacon_id: string;
  position: [number, number] | null;
  error: number | null;
  anchors_used: number;
}

interface RoomMapProps {
  anchors: Anchor[];
  positions: Position[];
  roomWidth: number;
  roomHeight: number;
}

const PAD = 52;

function RoomMap({ anchors, positions, roomWidth, roomHeight }: RoomMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  // Store latest props in a ref so the animation loop sees them without deps
  const propsRef = useRef({ anchors, positions, roomWidth, roomHeight });
  propsRef.current = { anchors, positions, roomWidth, roomHeight };

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    let cssW = 0;
    let cssH = 0;
    let resizePending = false;

    const applyResize = (w: number, h: number) => {
      if (w === 0 || h === 0) return;
      const dpr = window.devicePixelRatio || 1;
      cssW = w;
      cssH = h;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
    };

    const ro = new ResizeObserver((entries) => {
      if (resizePending) return;
      resizePending = true;
      // Schedule outside the current observation to avoid the loop error
      requestAnimationFrame(() => {
        resizePending = false;
        for (const entry of entries) {
          const bs = entry.borderBoxSize?.[0];
          if (bs) {
            applyResize(bs.inlineSize, bs.blockSize);
          } else {
            const rect = wrapper.getBoundingClientRect();
            applyResize(rect.width, rect.height);
          }
        }
      });
    });
    ro.observe(wrapper);

    // Initial size
    const rect = wrapper.getBoundingClientRect();
    applyResize(rect.width, rect.height);


    const draw = () => {
      if (cssW === 0 || cssH === 0) return;
      const dpr = window.devicePixelRatio || 1;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const { anchors, positions, roomWidth, roomHeight } = propsRef.current;

      // Scale context so all draw calls use CSS pixels
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const innerW = cssW - PAD * 2;
      const innerH = cssH - PAD * 2;
      const scale = Math.min(innerW / roomWidth, innerH / roomHeight);
      const roomPxW = roomWidth * scale;
      const roomPxH = roomHeight * scale;
      const ox = PAD + (innerW - roomPxW) / 2; // left edge of room
      const oy = PAD + (innerH - roomPxH) / 2; // top edge of room

      const toX = (mx: number) => ox + mx * scale;
      const toY = (my: number) => oy + (roomHeight - my) * scale; // Y-flip

      // ── Background ────────────────────────────────────────────────────────
      ctx.fillStyle = '#0a0a0f';
      ctx.fillRect(0, 0, cssW, cssH);

      // Room fill
      ctx.fillStyle = 'rgba(255,255,255,0.015)';
      ctx.fillRect(ox, oy, roomPxW, roomPxH);

      // ── Grid ──────────────────────────────────────────────────────────────
      ctx.strokeStyle = 'rgba(255,255,255,0.05)';
      ctx.lineWidth = 1;
      for (let mx = 0; mx <= roomWidth; mx++) {
        ctx.beginPath(); ctx.moveTo(toX(mx), oy); ctx.lineTo(toX(mx), oy + roomPxH); ctx.stroke();
      }
      for (let my = 0; my <= roomHeight; my++) {
        ctx.beginPath(); ctx.moveTo(ox, toY(my)); ctx.lineTo(ox + roomPxW, toY(my)); ctx.stroke();
      }

      // ── Room border ───────────────────────────────────────────────────────
      ctx.shadowBlur = 10;
      ctx.shadowColor = 'rgba(167,139,250,0.5)';
      ctx.strokeStyle = 'rgba(167,139,250,0.35)';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(ox, oy, roomPxW, roomPxH);
      ctx.shadowBlur = 0;

      // ── Axis labels ───────────────────────────────────────────────────────
      ctx.fillStyle = 'rgba(156,163,175,0.5)';
      ctx.font = "10px 'Fira Code',monospace";
      ctx.textAlign = 'center';
      const xStep = roomWidth <= 10 ? 2 : roomWidth <= 20 ? 4 : 5;
      const yStep = roomHeight <= 10 ? 2 : roomHeight <= 20 ? 4 : 5;
      for (let mx = 0; mx <= roomWidth; mx += xStep) {
        ctx.fillText(`${mx}m`, toX(mx), oy + roomPxH + 18);
      }
      ctx.textAlign = 'right';
      for (let my = 0; my <= roomHeight; my += yStep) {
        ctx.fillText(`${my}m`, ox - 8, toY(my) + 4);
      }

      const t = Date.now() * 0.003;

      // ── Anchors ───────────────────────────────────────────────────────────
      anchors.forEach((a) => {
        const cx = toX(a.x);
        const cy = toY(a.y);
        const color = a.online ? '#34d399' : '#f87171';
        const pulse = a.online ? Math.sin(t) * 3 : 0;

        // Halo
        ctx.fillStyle = a.online ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.1)';
        ctx.beginPath(); ctx.arc(cx, cy, 14 + pulse, 0, Math.PI * 2); ctx.fill();

        // Triangle
        ctx.shadowBlur = a.online ? 8 : 0;
        ctx.shadowColor = color;
        ctx.fillStyle = color;
        ctx.strokeStyle = '#0a0a0f';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 9);
        ctx.lineTo(cx - 8, cy + 6);
        ctx.lineTo(cx + 8, cy + 6);
        ctx.closePath();
        ctx.fill(); ctx.stroke();
        ctx.shadowBlur = 0;

        // Label
        ctx.fillStyle = '#e5e7eb';
        ctx.font = "bold 11px 'Outfit',sans-serif";
        ctx.textAlign = 'center';
        ctx.fillText(a.label || a.anchor_id, cx, cy + 22);
        ctx.fillStyle = 'rgba(156,163,175,0.55)';
        ctx.font = "9px 'Fira Code',monospace";
        ctx.fillText(`(${a.x}, ${a.y})`, cx, cy + 33);
      });

      // ── Beacons ───────────────────────────────────────────────────────────
      positions.forEach((pos) => {
        if (!pos.position) return;
        const cx = toX(pos.position[0]);
        const cy = toY(pos.position[1]);
        const pulse = Math.sin(t * 1.5) * 2;

        if (pos.error !== null) {
          const errPx = Math.max(10, pos.error * scale);
          ctx.setLineDash([4, 4]);
          ctx.strokeStyle = 'rgba(34,211,238,0.2)';
          ctx.fillStyle = 'rgba(34,211,238,0.04)';
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(cx, cy, errPx, 0, Math.PI * 2);
          ctx.fill(); ctx.stroke();
          ctx.setLineDash([]);
        }

        ctx.fillStyle = 'rgba(34,211,238,0.1)';
        ctx.beginPath(); ctx.arc(cx, cy, 14 + pulse, 0, Math.PI * 2); ctx.fill();

        ctx.strokeStyle = 'rgba(34,211,238,0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(cx, cy, 7 + pulse * 0.4, 0, Math.PI * 2); ctx.stroke();

        ctx.shadowBlur = 12;
        ctx.shadowColor = '#22d3ee';
        ctx.fillStyle = '#22d3ee';
        ctx.strokeStyle = '#0a0a0f';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.shadowBlur = 0;

        ctx.fillStyle = '#f8f9fa';
        ctx.font = "bold 10px 'Fira Code',monospace";
        ctx.textAlign = 'center';
        ctx.fillText(pos.beacon_id.slice(-8), cx, cy - 17);
        if (pos.error !== null) {
          ctx.fillStyle = 'rgba(156,163,175,0.7)';
          ctx.font = "9px 'Outfit',sans-serif";
          ctx.fillText(`±${pos.error.toFixed(2)}m`, cx, cy + 22);
        }
      });

      // ── Legend ────────────────────────────────────────────────────────────
      const lx = cssW - 155;
      const ly = 12;
      ctx.fillStyle = 'rgba(13,13,20,0.88)';
      ctx.strokeStyle = 'rgba(255,255,255,0.07)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(lx, ly, 145, 88, 8);
      else ctx.rect(lx, ly, 145, 88);
      ctx.fill(); ctx.stroke();

      ctx.fillStyle = '#e5e7eb';
      ctx.font = "bold 11px 'Outfit',sans-serif";
      ctx.textAlign = 'left';
      ctx.fillText('Legend', lx + 12, ly + 17);

      const items = [
        { color: '#34d399', label: 'Anchor (online)',  tri: true,  py: ly + 34 },
        { color: '#f87171', label: 'Anchor (offline)', tri: true,  py: ly + 54 },
        { color: '#22d3ee', label: 'Tracked Beacon',   tri: false, py: ly + 74 },
      ];
      items.forEach(({ color, label, tri, py }) => {
        ctx.fillStyle = color;
        if (tri) {
          ctx.beginPath();
          ctx.moveTo(lx + 17, py - 8); ctx.lineTo(lx + 11, py + 2); ctx.lineTo(lx + 23, py + 2);
          ctx.closePath(); ctx.fill();
        } else {
          ctx.beginPath(); ctx.arc(lx + 17, py - 2, 4, 0, Math.PI * 2); ctx.fill();
        }
        ctx.fillStyle = 'rgba(156,163,175,0.85)';
        ctx.font = "10px 'Outfit',sans-serif";
        ctx.fillText(label, lx + 30, py);
      });
    };

    const loop = () => {
      draw();
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
    };
  }, []); // only mount/unmount — props are read via ref

  return (
    <div ref={wrapperRef} className="room-map-wrapper">
      <canvas ref={canvasRef} className="room-map-canvas" />
    </div>
  );
}

export default RoomMap;
