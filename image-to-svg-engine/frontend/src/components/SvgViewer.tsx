import { useRef, useState } from "react";
import type { WheelEvent as ReactWheelEvent, MouseEvent as ReactMouseEvent } from "react";
import type { DetectedObject } from "../types";

interface Props {
  svg: string;
  viewBox: string;
  objects: DetectedObject[];
  originalImageUrl: string | null;
}

const MIN_SCALE = 0.25;
const MAX_SCALE = 8;

/**
 * Renders the generated SVG inside a pan/zoom viewport. The SVG itself is
 * injected via dangerouslySetInnerHTML because it is a complete, trusted
 * document we generated ourselves (not user-supplied markup) - this keeps
 * native <path>/<polygon> rendering pixel-perfect instead of re-deriving
 * shapes with a canvas.
 */
export default function SvgViewer({ svg, viewBox, objects, originalImageUrl }: Props) {
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [showOverlay, setShowOverlay] = useState(false);
  const [showPoints, setShowPoints] = useState(false);
  const dragState = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);

  const [, , vbWidth, vbHeight] = viewBox.split(" ").map(Number);

  const handleWheel = (e: ReactWheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const delta = -e.deltaY * 0.0015;
    setScale((prev) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev + prev * delta)));
  };

  const handleMouseDown = (e: ReactMouseEvent<HTMLDivElement>) => {
    dragState.current = { startX: e.clientX, startY: e.clientY, originX: offset.x, originY: offset.y };
  };

  const handleMouseMove = (e: ReactMouseEvent<HTMLDivElement>) => {
    if (!dragState.current) return;
    const dx = e.clientX - dragState.current.startX;
    const dy = e.clientY - dragState.current.startY;
    setOffset({ x: dragState.current.originX + dx, y: dragState.current.originY + dy });
  };

  const stopDrag = () => {
    dragState.current = null;
  };

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <button
          onClick={() => setScale((s) => Math.min(MAX_SCALE, s * 1.25))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 hover:bg-slate-50"
        >
          Zoom in
        </button>
        <button
          onClick={() => setScale((s) => Math.max(MIN_SCALE, s / 1.25))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 hover:bg-slate-50"
        >
          Zoom out
        </button>
        <button onClick={reset} className="rounded-md border border-slate-300 bg-white px-2 py-1 hover:bg-slate-50">
          Reset
        </button>
        <span className="text-slate-400">{Math.round(scale * 100)}%</span>
        <label className="ml-2 flex items-center gap-1 text-slate-600">
          <input type="checkbox" checked={showPoints} onChange={(e) => setShowPoints(e.target.checked)} />
          Show points
        </label>
        {originalImageUrl && (
          <label className="flex items-center gap-1 text-slate-600">
            <input type="checkbox" checked={showOverlay} onChange={(e) => setShowOverlay(e.target.checked)} />
            Overlay original
          </label>
        )}
      </div>

      <div
        className="relative h-[420px] w-full cursor-grab overflow-hidden rounded-lg bg-checkerboard active:cursor-grabbing"
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={stopDrag}
        onMouseLeave={stopDrag}
      >
        <div
          className="absolute left-1/2 top-1/2 origin-center"
          style={{
            transform: `translate(-50%, -50%) translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
          }}
        >
          {showOverlay && originalImageUrl && (
            <img
              src={originalImageUrl}
              alt="Original overlay"
              className="pointer-events-none absolute inset-0 h-full w-full object-contain opacity-40"
              style={{ width: vbWidth, height: vbHeight }}
            />
          )}
          <div style={{ width: vbWidth, height: vbHeight }} dangerouslySetInnerHTML={{ __html: svg }} />
          {showPoints &&
            objects.map((obj) =>
              obj.points_svg.map((p, i) => (
                <div
                  key={`${obj.id}-${i}`}
                  className="absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-brand-600"
                  style={{ left: p.x, top: p.y }}
                  title={`(${p.x.toFixed(1)}, ${p.y.toFixed(1)})`}
                />
              )),
            )}
        </div>
      </div>
    </div>
  );
}
