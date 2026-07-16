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

export interface Zone {
  name: string;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

export interface ZoneBounds {
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
}

export interface HeatPoint {
  x: number;
  y: number;
  value: number;
}

interface RoomMapProps {
  anchors: Anchor[];
  positions: Position[];
  roomWidth: number;
  roomHeight: number;
  zones?: Zone[];
  /** When true, click-drag on the canvas draws a new zone rectangle. */
  editable?: boolean;
  /** The zone currently being edited/drawn — rendered with a dashed outline. */
  draftZone?: ZoneBounds | null;
  /** Fired continuously while dragging (and once on release) with meter bounds, rounded to 0.1m. */
  onZoneDraw?: (bounds: ZoneBounds) => void;
  /** Dwelling-time heat points to overlay (e.g. from the heatmap analysis), in the same room coordinate space. */
  heatPoints?: HeatPoint[];
  heatMaxValue?: number;
}

const PAD = 52;
const MIN_CANVAS_WIDTH = 320;
const MIN_CANVAS_HEIGHT = 320;

// Light-minimalist palette (kept in sync with style.css CSS variables)
const COLORS = {
  bg: '#ffffff',
  roomFill: 'rgba(109,94,248,0.012)',
  grid: 'rgba(23,23,28,0.06)',
  roomBorder: 'rgba(109,94,248,0.32)',
  axisLabel: 'rgba(107,107,118,0.8)',
  anchorOnline: '#16a34a',
  anchorOffline: '#dc2626',
  anchorHaloOnline: 'rgba(22,163,74,0.12)',
  anchorHaloOffline: 'rgba(220,38,38,0.1)',
  labelMain: '#17171c',
  labelMuted: 'rgba(107,107,118,0.85)',
  beacon: '#0891b2',
  beaconHalo: 'rgba(8,145,178,0.12)',
  beaconRing: 'rgba(8,145,178,0.35)',
  zoneFill: 'rgba(109,94,248,0.025)',
  zoneBorder: 'rgba(109,94,248,0.2)',
  zoneLabel: '#6d5ef8',
  draftFill: 'rgba(217,119,6,0.08)',
  draftBorder: '#d97706',
  legendBg: 'rgba(255,255,255,0.92)',
  legendBorder: 'rgba(23,23,28,0.08)',
};

function round1(n: number) {
  return Math.round(n * 10) / 10;
}

function RoomMap({ anchors, positions, roomWidth, roomHeight, zones = [], editable = false, draftZone = null, onZoneDraw, heatPoints = [], heatMaxValue = 0 }: RoomMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  // Store latest props in a ref so the animation loop sees them without deps
  const propsRef = useRef({ anchors, positions, roomWidth, roomHeight, zones, draftZone, heatPoints, heatMaxValue });
  propsRef.current = { anchors, positions, roomWidth, roomHeight, zones, draftZone, heatPoints, heatMaxValue };

  // Latest meter<->pixel transform, updated every draw frame, used by drag handlers
  const transformRef = useRef({ scale: 1, ox: 0, oy: 0, roomWidth: 10, roomHeight: 8 });
  const draggingRef = useRef<{ x0: number; y0: number } | null>(null);
  const onZoneDrawRef = useRef(onZoneDraw);
  onZoneDrawRef.current = onZoneDraw;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;

    let cssW = 0;
    let cssH = 0;
    let resizePending = false;

    const applyResize = (w: number, h: number) => {
      if (w <= 0 || h <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      cssW = w;
      cssH = h;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
    };

    const measureAndResize = () => {
      const rect = wrapper.getBoundingClientRect();
      const nextW = Math.max(rect.width || wrapper.clientWidth, MIN_CANVAS_WIDTH);
      const nextH = Math.max(rect.height || wrapper.clientHeight, MIN_CANVAS_HEIGHT);

      if (Math.round(nextW) !== Math.round(cssW) || Math.round(nextH) !== Math.round(cssH)) {
        applyResize(nextW, nextH);
      }
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
            measureAndResize();
          }
        }
      });
    });
    ro.observe(wrapper);

    // Initial size
    measureAndResize();

    const draw = () => {
      measureAndResize();
      if (cssW === 0 || cssH === 0) return;
      const dpr = window.devicePixelRatio || 1;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const { anchors, positions, roomWidth, roomHeight, zones, draftZone, heatPoints, heatMaxValue } = propsRef.current;

      // Scale context so all draw calls use CSS pixels
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const innerW = Math.max(1, cssW - PAD * 2);
      const innerH = Math.max(1, cssH - PAD * 2);
      const scale = Math.min(innerW / roomWidth, innerH / roomHeight);
      const roomPxW = roomWidth * scale;
      const roomPxH = roomHeight * scale;
      const ox = PAD + (innerW - roomPxW) / 2; // left edge of room
      const oy = PAD + (innerH - roomPxH) / 2; // top edge of room

      transformRef.current = { scale, ox, oy, roomWidth, roomHeight };

      const toX = (mx: number) => ox + mx * scale;
      const toY = (my: number) => oy + (roomHeight - my) * scale; // Y-flip
      const roomBottom = oy + roomPxH;

      // Draws centered text but slides it inward so it never overflows the canvas edges.
      const fillTextClamped = (text: string, x: number, y: number, margin = 6) => {
        const w = ctx.measureText(text).width;
        const clampedX = Math.min(Math.max(x, margin + w / 2), cssW - margin - w / 2);
        ctx.textAlign = 'center';
        ctx.fillText(text, clampedX, y);
      };

      // ── Background ────────────────────────────────────────────────────────
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, cssW, cssH);

      // Room fill
      ctx.fillStyle = COLORS.roomFill;
      ctx.fillRect(ox, oy, roomPxW, roomPxH);

      // ── Grid ──────────────────────────────────────────────────────────────
      ctx.strokeStyle = COLORS.grid;
      ctx.lineWidth = 1;
      for (let mx = 0; mx <= roomWidth; mx++) {
        ctx.beginPath(); ctx.moveTo(toX(mx), oy); ctx.lineTo(toX(mx), oy + roomPxH); ctx.stroke();
      }
      for (let my = 0; my <= roomHeight; my++) {
        ctx.beginPath(); ctx.moveTo(ox, toY(my)); ctx.lineTo(ox + roomPxW, toY(my)); ctx.stroke();
      }

      // ── Room border ───────────────────────────────────────────────────────
      ctx.strokeStyle = COLORS.roomBorder;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(ox, oy, roomPxW, roomPxH);

      // ── Zones ─────────────────────────────────────────────────────────────
      // Clamp to the room's actual bounds — stale zone data (e.g. from before the room was
      // resized) must never visually escape the room box and overlap other UI elements.
      (zones || []).forEach((z) => {
        const x_min = Math.max(0, Math.min(z.x_min, roomWidth));
        const x_max = Math.max(0, Math.min(z.x_max, roomWidth));
        const y_min = Math.max(0, Math.min(z.y_min, roomHeight));
        const y_max = Math.max(0, Math.min(z.y_max, roomHeight));
        if (x_max <= x_min || y_max <= y_min) return;

        const zx = toX(x_min);
        const zy = toY(y_max);
        const zw = (x_max - x_min) * scale;
        const zh = (y_max - y_min) * scale;
        ctx.fillStyle = COLORS.zoneFill;
        ctx.fillRect(zx, zy, zw, zh);
        ctx.strokeStyle = COLORS.zoneBorder;
        ctx.lineWidth = 1;
        ctx.strokeRect(zx, zy, zw, zh);
        if (zw > 30 && zh > 16) {
          ctx.font = "600 11px 'Outfit',sans-serif";
          const labelCx = Math.min(Math.max(zx + zw / 2, zx + 4), zx + zw - 4);
          const labelW = Math.min(ctx.measureText(z.name).width, zw - 8);
          // Solid chip behind the name so it stays legible over the grid and any neighboring zone.
          ctx.fillStyle = COLORS.bg;
          ctx.fillRect(labelCx - labelW / 2 - 5, zy + zh / 2 - 10, labelW + 10, 18);
          ctx.fillStyle = COLORS.zoneLabel;
          ctx.textAlign = 'center';
          ctx.save();
          ctx.beginPath();
          ctx.rect(zx, zy, zw, zh);
          ctx.clip();
          ctx.fillText(z.name, labelCx, zy + zh / 2 + 4);
          ctx.restore();
        }
      });

      // ── Draft zone (being drawn/edited) ──────────────────────────────────
      if (draftZone) {
        const zx = toX(draftZone.x_min);
        const zy = toY(draftZone.y_max);
        const zw = (draftZone.x_max - draftZone.x_min) * scale;
        const zh = (draftZone.y_max - draftZone.y_min) * scale;
        ctx.fillStyle = COLORS.draftFill;
        ctx.fillRect(zx, zy, zw, zh);
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = COLORS.draftBorder;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(zx, zy, zw, zh);
        ctx.setLineDash([]);
      }

      // ── Heatmap overlay (dwelling-time points, if provided) ─────────────────
      if (heatPoints.length > 0 && heatMaxValue > 0) {
        // Heat points sit on a 0.5m grid — keep the blob close to that cell instead of smearing into neighbors.
        const blobRadius = Math.max(10, scale * 0.3);
        heatPoints.forEach((p) => {
          const cx = toX(p.x);
          const cy = toY(p.y);
          const intensity = p.value / heatMaxValue;

          let colorStr;
          if (intensity > 0.7) colorStr = `rgba(220, 38, 38, ${intensity * 0.75})`;
          else if (intensity > 0.4) colorStr = `rgba(217, 119, 6, ${intensity * 0.7})`;
          else colorStr = `rgba(22, 163, 74, ${Math.max(intensity, 0.25) * 0.65})`;

          const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, blobRadius);
          grad.addColorStop(0, colorStr);
          grad.addColorStop(1, 'rgba(0,0,0,0)');

          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(cx, cy, blobRadius, 0, 2 * Math.PI);
          ctx.fill();
        });
      }

      // ── Axis labels ───────────────────────────────────────────────────────
      ctx.fillStyle = COLORS.axisLabel;
      ctx.font = "10px 'Fira Code',monospace";
      ctx.textAlign = 'center';
      const xStep = roomWidth <= 10 ? 2 : roomWidth <= 20 ? 4 : 5;
      const yStep = roomHeight <= 10 ? 2 : roomHeight <= 20 ? 4 : 5;
      for (let mx = 0; mx <= roomWidth; mx += xStep) {
        ctx.fillText(`${mx}m`, toX(mx), roomBottom + 28);
      }
      ctx.textAlign = 'right';
      for (let my = 0; my <= roomHeight; my += yStep) {
        if (my === 0) continue; // the x-axis already labels the shared (0,0) corner
        ctx.fillText(`${my}m`, ox - 8, toY(my) + 4);
      }

      const t = Date.now() * 0.003;

      // ── Anchors ───────────────────────────────────────────────────────────
      anchors.forEach((a) => {
        const cx = toX(a.x);
        const cy = toY(a.y);
        const color = a.online ? COLORS.anchorOnline : COLORS.anchorOffline;
        const pulse = a.online ? Math.sin(t) * 2 : 0;

        // Halo
        ctx.fillStyle = a.online ? COLORS.anchorHaloOnline : COLORS.anchorHaloOffline;
        ctx.beginPath(); ctx.arc(cx, cy, 13 + pulse, 0, Math.PI * 2); ctx.fill();

        // Triangle
        ctx.fillStyle = color;
        ctx.strokeStyle = COLORS.bg;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 9);
        ctx.lineTo(cx - 8, cy + 6);
        ctx.lineTo(cx + 8, cy + 6);
        ctx.closePath();
        ctx.fill(); ctx.stroke();

        // Label. Edge anchors use inward/outward labels so they do not collide with axis text or room zones.
        const nearBottom = cy > roomBottom - 26;
        const nearTop = cy < oy + 26;
        
        let labelY = cy + 24;
        let coordY = cy + 36;
        let shouldDrawCoord = true;

        if (nearBottom) {
          labelY = cy - 22;
          coordY = cy - 10;
        } else if (nearTop) {
          labelY = cy - 16;
          coordY = cy - 28;
        }

        ctx.fillStyle = COLORS.labelMain;
        ctx.font = "bold 11px 'Outfit',sans-serif";
        fillTextClamped(a.label || a.anchor_id, cx, labelY);
        if (shouldDrawCoord) {
          ctx.fillStyle = COLORS.labelMuted;
          ctx.font = "9px 'Fira Code',monospace";
          fillTextClamped(`(${a.x}, ${a.y})`, cx, coordY);
        }
      });

      // ── Beacons ───────────────────────────────────────────────────────────
      positions.forEach((pos) => {
        if (!pos.position) return;
        const cx = toX(pos.position[0]);
        const cy = toY(pos.position[1]);
        const pulse = Math.sin(t * 1.5) * 1.5;

        if (pos.error !== null) {
          const errPx = Math.max(10, pos.error * scale);
          ctx.setLineDash([4, 4]);
          ctx.strokeStyle = 'rgba(8,145,178,0.25)';
          ctx.fillStyle = 'rgba(8,145,178,0.04)';
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.arc(cx, cy, errPx, 0, Math.PI * 2);
          ctx.fill(); ctx.stroke();
          ctx.setLineDash([]);
        }

        ctx.fillStyle = COLORS.beaconHalo;
        ctx.beginPath(); ctx.arc(cx, cy, 13 + pulse, 0, Math.PI * 2); ctx.fill();

        ctx.strokeStyle = COLORS.beaconRing;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(cx, cy, 7 + pulse * 0.4, 0, Math.PI * 2); ctx.stroke();

        ctx.fillStyle = COLORS.beacon;
        ctx.strokeStyle = COLORS.bg;
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();

        ctx.fillStyle = COLORS.labelMain;
        ctx.font = "bold 10px 'Fira Code',monospace";
        fillTextClamped(pos.beacon_id.slice(-8), cx, cy - 17);
        if (pos.error !== null) {
          ctx.fillStyle = COLORS.labelMuted;
          ctx.font = "9px 'Outfit',sans-serif";
          fillTextClamped(`±${pos.error.toFixed(2)}m`, cx, cy + 22);
        }
      });

      // ── Legend ────────────────────────────────────────────────────────────
      if (cssW >= 520) {
        const legendW = 132;
        const legendH = 78;
        const lx = Math.max(12, cssW - legendW - 12);
        const ly = Math.max(12, oy + 12);
        ctx.fillStyle = COLORS.legendBg;
        ctx.strokeStyle = COLORS.legendBorder;
        ctx.lineWidth = 1;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(lx, ly, legendW, legendH, 8);
        else ctx.rect(lx, ly, legendW, legendH);
        ctx.fill(); ctx.stroke();

        ctx.fillStyle = COLORS.labelMain;
        ctx.font = "bold 10px 'Outfit',sans-serif";
        ctx.textAlign = 'left';
        ctx.fillText('Legend', lx + 10, ly + 15);

        const items = [
          { color: COLORS.anchorOnline, label: 'Anchor online', tri: true, py: ly + 30 },
          { color: COLORS.anchorOffline, label: 'Anchor offline', tri: true, py: ly + 48 },
          { color: COLORS.beacon, label: 'Beacon', tri: false, py: ly + 66 },
        ];
        items.forEach(({ color, label, tri, py }) => {
          ctx.fillStyle = color;
          if (tri) {
            ctx.beginPath();
            ctx.moveTo(lx + 15, py - 7); ctx.lineTo(lx + 10, py + 1); ctx.lineTo(lx + 20, py + 1);
            ctx.closePath(); ctx.fill();
          } else {
            ctx.beginPath(); ctx.arc(lx + 15, py - 2, 4, 0, Math.PI * 2); ctx.fill();
          }
          ctx.fillStyle = COLORS.labelMuted;
          ctx.font = "9px 'Outfit',sans-serif";
          ctx.fillText(label, lx + 27, py);
        });
      }
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

  // Draw-to-calibrate: click-drag on the canvas to define a zone rectangle in meters.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !editable) return;

    const pxToMeters = (px: number, py: number) => {
      const { scale, ox, oy, roomWidth, roomHeight } = transformRef.current;
      const mx = (px - ox) / scale;
      const my = roomHeight - (py - oy) / scale;
      return {
        mx: Math.min(Math.max(mx, 0), roomWidth),
        my: Math.min(Math.max(my, 0), roomHeight),
      };
    };

    const emit = (x0: number, y0: number, x1: number, y1: number) => {
      const bounds: ZoneBounds = {
        x_min: round1(Math.min(x0, x1)),
        x_max: round1(Math.max(x0, x1)),
        y_min: round1(Math.min(y0, y1)),
        y_max: round1(Math.max(y0, y1)),
      };
      onZoneDrawRef.current?.(bounds);
    };

    const handleDown = (e: MouseEvent) => {
      const { mx, my } = pxToMeters(e.offsetX, e.offsetY);
      draggingRef.current = { x0: mx, y0: my };
    };
    const handleMove = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const { mx, my } = pxToMeters(e.offsetX, e.offsetY);
      emit(draggingRef.current.x0, draggingRef.current.y0, mx, my);
    };
    const handleUp = (e: MouseEvent) => {
      if (!draggingRef.current) return;
      const { mx, my } = pxToMeters(e.offsetX, e.offsetY);
      emit(draggingRef.current.x0, draggingRef.current.y0, mx, my);
      draggingRef.current = null;
    };
    const handleLeave = () => {
      draggingRef.current = null;
    };

    canvas.addEventListener('mousedown', handleDown);
    canvas.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    canvas.addEventListener('mouseleave', handleLeave);
    canvas.style.cursor = 'crosshair';

    return () => {
      canvas.removeEventListener('mousedown', handleDown);
      canvas.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
      canvas.removeEventListener('mouseleave', handleLeave);
      canvas.style.cursor = '';
    };
  }, [editable]);

  return (
    <div ref={wrapperRef} className="room-map-wrapper">
      <canvas ref={canvasRef} className="room-map-canvas" />
    </div>
  );
}

export default RoomMap;
