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

const PADDING = 60;
const SCALE_FACTOR = 50; // pixels per meter

function RoomMap({ anchors, positions, roomWidth, roomHeight }: RoomMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const canvasWidth = roomWidth * SCALE_FACTOR + PADDING * 2;
  const canvasHeight = roomHeight * SCALE_FACTOR + PADDING * 2;

  // Convert world coordinates (meters) to canvas coordinates (pixels)
  const worldToCanvas = (x: number, y: number): [number, number] => {
    return [
      PADDING + x * SCALE_FACTOR,
      canvasHeight - PADDING - y * SCALE_FACTOR, // Flip Y axis
    ];
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);

    // Draw room background
    const [roomX, roomY] = worldToCanvas(0, roomHeight);
    const [roomX2, roomY2] = worldToCanvas(roomWidth, 0);
    
    ctx.fillStyle = '#f8f9fa';
    ctx.fillRect(roomX, roomY, roomX2 - roomX, roomY2 - roomY);
    
    // Draw grid
    ctx.strokeStyle = '#e9ecef';
    ctx.lineWidth = 1;
    
    for (let x = 0; x <= roomWidth; x++) {
      const [cx, cy1] = worldToCanvas(x, 0);
      const [, cy2] = worldToCanvas(x, roomHeight);
      ctx.beginPath();
      ctx.moveTo(cx, cy1);
      ctx.lineTo(cx, cy2);
      ctx.stroke();
    }
    
    for (let y = 0; y <= roomHeight; y++) {
      const [cx1, cy] = worldToCanvas(0, y);
      const [cx2] = worldToCanvas(roomWidth, y);
      ctx.beginPath();
      ctx.moveTo(cx1, cy);
      ctx.lineTo(cx2, cy);
      ctx.stroke();
    }

    // Draw room border
    ctx.strokeStyle = '#495057';
    ctx.lineWidth = 2;
    ctx.strokeRect(roomX, roomY, roomX2 - roomX, roomY2 - roomY);

    // Draw scale indicators
    ctx.fillStyle = '#6c757d';
    ctx.font = '11px monospace';
    ctx.textAlign = 'center';
    for (let x = 0; x <= roomWidth; x += 2) {
      const [cx, cy] = worldToCanvas(x, 0);
      ctx.fillText(`${x}m`, cx, cy + 20);
    }
    ctx.textAlign = 'right';
    for (let y = 0; y <= roomHeight; y += 2) {
      const [cx, cy] = worldToCanvas(0, y);
      ctx.fillText(`${y}m`, cx - 10, cy + 4);
    }

    // Draw anchors as triangles
    anchors.forEach((anchor) => {
      const [cx, cy] = worldToCanvas(anchor.x, anchor.y);
      
      ctx.fillStyle = anchor.online ? '#28a745' : '#dc3545';
      ctx.strokeStyle = anchor.online ? '#155724' : '#721c24';
      ctx.lineWidth = 2;

      // Draw triangle
      ctx.beginPath();
      ctx.moveTo(cx, cy - 15);
      ctx.lineTo(cx - 12, cy + 10);
      ctx.lineTo(cx + 12, cy + 10);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Draw label
      ctx.fillStyle = '#212529';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(anchor.label || anchor.anchor_id, cx, cy + 28);
      
      // Draw coordinates
      ctx.fillStyle = '#6c757d';
      ctx.font = '10px monospace';
      ctx.fillText(`(${anchor.x}, ${anchor.y})`, cx, cy + 42);
    });

    // Draw beacon positions
    positions.forEach((pos) => {
      if (!pos.position) return;

      const [cx, cy] = worldToCanvas(pos.position[0], pos.position[1]);

      // Draw position uncertainty circle
      if (pos.error !== null) {
        const radius = Math.max(5, pos.error * SCALE_FACTOR);
        ctx.fillStyle = 'rgba(0, 123, 255, 0.15)';
        ctx.strokeStyle = 'rgba(0, 123, 255, 0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      // Draw beacon dot
      ctx.fillStyle = '#007bff';
      ctx.strokeStyle = '#0056b3';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Draw beacon ID (shortened MAC)
      const shortId = pos.beacon_id.slice(-8);
      ctx.fillStyle = '#212529';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(shortId, cx, cy - 14);

      // Draw error value
      if (pos.error !== null) {
        ctx.fillStyle = '#6c757d';
        ctx.fillText(`err: ${pos.error.toFixed(2)}m`, cx, cy + 24);
      }
    });

    // Draw legend
    const legendX = canvasWidth - 150;
    const legendY = 20;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(legendX, legendY, 140, 80);
    ctx.strokeStyle = '#dee2e6';
    ctx.strokeRect(legendX, legendY, 140, 80);

    ctx.font = 'bold 11px sans-serif';
    ctx.fillStyle = '#212529';
    ctx.textAlign = 'left';
    ctx.fillText('Legend', legendX + 10, legendY + 16);

    // Anchor online
    ctx.fillStyle = '#28a745';
    ctx.beginPath();
    ctx.moveTo(legendX + 16, legendY + 30);
    ctx.lineTo(legendX + 10, legendY + 40);
    ctx.lineTo(legendX + 22, legendY + 40);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = '#212529';
    ctx.font = '10px sans-serif';
    ctx.fillText('Anchor (online)', legendX + 28, legendY + 38);

    // Beacon
    ctx.fillStyle = '#007bff';
    ctx.beginPath();
    ctx.arc(legendX + 16, legendY + 55, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#212529';
    ctx.fillText('Beacon', legendX + 28, legendY + 58);

    // Anchor offline
    ctx.fillStyle = '#dc3545';
    ctx.beginPath();
    ctx.moveTo(legendX + 16, legendY + 66);
    ctx.lineTo(legendX + 10, legendY + 76);
    ctx.lineTo(legendX + 22, legendY + 76);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = '#212529';
    ctx.fillText('Anchor (offline)', legendX + 28, legendY + 74);

  }, [anchors, positions, roomWidth, roomHeight, canvasWidth, canvasHeight]);

  return (
    <div className="room-map">
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        style={{ border: '1px solid #dee2e6', borderRadius: '8px' }}
      />
    </div>
  );
}

export default RoomMap;
