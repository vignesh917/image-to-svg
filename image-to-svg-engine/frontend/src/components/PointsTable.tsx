import type { DetectedObject } from "../types";

interface Props {
  objects: DetectedObject[];
}

export default function PointsTable({ objects }: Props) {
  return (
    <div className="space-y-2">
      {objects.map((obj) => (
        <details key={obj.id} className="rounded-lg border border-slate-200 bg-white" open={objects.length === 1}>
          <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-slate-700">
            Object #{obj.id} - {obj.point_count} points (simplified from {obj.raw_point_count}) - area{" "}
            {Math.round(obj.area).toLocaleString()}px²
          </summary>
          <div className="max-h-48 overflow-y-auto border-t border-slate-100 px-3 py-2">
            <div className="mb-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-[11px] text-slate-500">
              <span>
                Bounding box: {Math.round(obj.bounding_box.width)} x {Math.round(obj.bounding_box.height)}px
              </span>
              <span>Perimeter: {Math.round(obj.perimeter)}px</span>
            </div>
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className="text-slate-400">
                  <th className="pr-3 font-normal">#</th>
                  <th className="pr-3 font-normal">x (px)</th>
                  <th className="font-normal">y (px)</th>
                </tr>
              </thead>
              <tbody className="font-mono text-slate-600">
                {obj.points.map((p, i) => (
                  <tr key={i}>
                    <td className="pr-3">{i}</td>
                    <td className="pr-3">{p.x.toFixed(2)}</td>
                    <td>{p.y.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </div>
  );
}
