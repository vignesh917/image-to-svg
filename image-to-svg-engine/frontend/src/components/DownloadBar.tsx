import { useState } from "react";
import type { ProcessingResult } from "../types";

interface Props {
  result: ProcessingResult;
  baseFileName: string;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Rasterize the generated SVG to a PNG client-side via an offscreen canvas -
 * no backend round-trip needed for this bonus export. */
async function svgToPngBlob(svg: string, width: number, height: number, scale = 2): Promise<Blob> {
  const svgBlob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = url;
    });

    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D context unavailable.");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("PNG export failed."))), "image/png");
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function DownloadBar({ result, baseFileName }: Props) {
  const [busy, setBusy] = useState(false);

  const downloadSvg = () => {
    downloadBlob(new Blob([result.svg], { type: "image/svg+xml" }), `${baseFileName}.svg`);
  };

  const downloadJson = () => {
    const payload = {
      image_size: result.image_size,
      view_box: result.view_box,
      params_used: result.params_used,
      objects: result.objects.map((o) => ({
        id: o.id,
        area: o.area,
        perimeter: o.perimeter,
        point_count: o.point_count,
        bounding_box: o.bounding_box,
        points: o.points,
        points_normalized: o.points_normalized,
      })),
    };
    downloadBlob(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      `${baseFileName}.json`,
    );
  };

  const downloadPng = async () => {
    setBusy(true);
    try {
      const [, , w, h] = result.view_box.split(" ").map(Number);
      const blob = await svgToPngBlob(result.svg, w, h);
      downloadBlob(blob, `${baseFileName}.png`);
    } catch {
      // eslint-disable-next-line no-alert
      alert("Could not export PNG from the generated SVG.");
    } finally {
      setBusy(false);
    }
  };

  const buttonClass =
    "rounded-md bg-brand-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50";

  return (
    <div className="flex flex-wrap gap-2">
      <button onClick={downloadSvg} className={buttonClass}>
        Download SVG
      </button>
      <button onClick={downloadJson} className={buttonClass}>
        Download JSON
      </button>
      <button onClick={downloadPng} disabled={busy} className={buttonClass}>
        {busy ? "Rendering…" : "Download PNG"}
      </button>
    </div>
  );
}
