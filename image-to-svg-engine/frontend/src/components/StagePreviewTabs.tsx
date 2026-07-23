import { useState } from "react";
import type { StageKey, StagePreviews } from "../types";
import { STAGE_LABELS } from "../types";

interface Props {
  stages: StagePreviews;
}

const ORDER: StageKey[] = ["original", "grayscale", "blurred", "threshold", "edges", "contours_overlay"];

export default function StagePreviewTabs({ stages }: Props) {
  const [active, setActive] = useState<StageKey>("original");

  return (
    <div>
      <div className="flex flex-wrap gap-1 border-b border-slate-200 pb-2">
        {ORDER.map((key) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={[
              "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
              active === key ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
            ].join(" ")}
          >
            {STAGE_LABELS[key]}
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-center overflow-hidden rounded-lg bg-checkerboard">
        <img
          src={stages[active]}
          alt={`${STAGE_LABELS[active]} preview`}
          className="max-h-[420px] w-full object-contain"
        />
      </div>
    </div>
  );
}
