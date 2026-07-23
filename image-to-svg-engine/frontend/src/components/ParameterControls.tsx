import type { ReactNode } from "react";
import type { ProcessingParams, ThresholdMode } from "../types";

interface Props {
  params: ProcessingParams;
  onChange: (patch: Partial<ProcessingParams>) => void;
  disabled?: boolean;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-3 border-b border-slate-200 py-4 first:pt-0 last:border-b-0">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </div>
  );
}

function SliderRow({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  hint?: string;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span className="font-mono text-slate-500">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-brand-600 disabled:opacity-40"
      />
      {hint && <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p>}
    </label>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center justify-between text-xs text-slate-600">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-brand-600 disabled:opacity-40"
      />
    </label>
  );
}

export default function ParameterControls({ params, onChange, disabled }: Props) {
  return (
    <div className="text-slate-800">
      <Section title="Denoise / Blur">
        <SliderRow
          label="Gaussian blur kernel"
          value={params.blur_kernel}
          min={1}
          max={31}
          step={2}
          onChange={(v) => onChange({ blur_kernel: v })}
          disabled={disabled}
        />
      </Section>

      <Section title="Threshold">
        <label className="block">
          <span className="mb-1 block text-xs text-slate-600">Mode</span>
          <select
            value={params.threshold_mode}
            disabled={disabled}
            onChange={(e) => onChange({ threshold_mode: e.target.value as ThresholdMode })}
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm disabled:opacity-40"
          >
            <option value="adaptive">Adaptive (mean)</option>
            <option value="sauvola">Sauvola (uneven lighting)</option>
            <option value="otsu">Otsu (global)</option>
            <option value="binary">Fixed binary</option>
          </select>
        </label>
        {(params.threshold_mode === "adaptive" || params.threshold_mode === "sauvola") && (
          <SliderRow
            label="Block / window size"
            value={params.adaptive_block_size}
            min={3}
            max={199}
            step={2}
            onChange={(v) => onChange({ adaptive_block_size: v })}
            disabled={disabled}
          />
        )}
        {params.threshold_mode === "adaptive" && (
          <SliderRow
            label="Adaptive C"
            value={params.adaptive_c}
            min={-50}
            max={50}
            onChange={(v) => onChange({ adaptive_c: v })}
            disabled={disabled}
          />
        )}
        {params.threshold_mode === "sauvola" && (
          <SliderRow
            label="Sauvola k"
            value={params.sauvola_k}
            min={0.01}
            max={1}
            step={0.01}
            onChange={(v) => onChange({ sauvola_k: v })}
            disabled={disabled}
          />
        )}
        <ToggleRow
          label="Invert (shape darker than background)"
          checked={params.invert}
          onChange={(v) => onChange({ invert: v })}
          disabled={disabled}
        />
      </Section>

      <Section title="Edges &amp; morphology">
        <ToggleRow
          label="Auto Canny thresholds"
          checked={params.auto_canny}
          onChange={(v) => onChange({ auto_canny: v })}
          disabled={disabled}
        />
        {!params.auto_canny && (
          <>
            <SliderRow
              label="Canny low"
              value={params.canny_low}
              min={0}
              max={500}
              onChange={(v) => onChange({ canny_low: v })}
              disabled={disabled}
            />
            <SliderRow
              label="Canny high"
              value={params.canny_high}
              min={0}
              max={500}
              onChange={(v) => onChange({ canny_high: v })}
              disabled={disabled}
            />
          </>
        )}
        <SliderRow
          label="Morphological closing kernel"
          value={params.morph_kernel}
          min={0}
          max={31}
          step={2}
          onChange={(v) => onChange({ morph_kernel: v })}
          disabled={disabled}
        />
      </Section>

      <Section title="Contour">
        <SliderRow
          label="Simplification (Douglas-Peucker epsilon)"
          value={params.epsilon_factor}
          min={0.0005}
          max={0.05}
          step={0.0005}
          onChange={(v) => onChange({ epsilon_factor: v })}
          disabled={disabled}
          hint="Lower = more points / higher fidelity. Higher = fewer points / simpler shape."
        />
        <SliderRow
          label="Minimum area ratio"
          value={params.min_area_ratio}
          min={0}
          max={0.2}
          step={0.001}
          onChange={(v) => onChange({ min_area_ratio: v })}
          disabled={disabled}
          hint="Ignore contours smaller than this fraction of the image."
        />
        <ToggleRow
          label="Smoothing (Chaikin)"
          checked={params.smoothing}
          onChange={(v) => onChange({ smoothing: v })}
          disabled={disabled}
        />
        <ToggleRow
          label="Convex hull"
          checked={params.use_convex_hull}
          onChange={(v) => onChange({ use_convex_hull: v })}
          disabled={disabled}
        />
        <ToggleRow
          label="Remove background (flood-fill)"
          checked={params.remove_background}
          onChange={(v) => onChange({ remove_background: v })}
          disabled={disabled}
        />
        <ToggleRow
          label="Multi-object detection"
          checked={params.multi_object}
          onChange={(v) => onChange({ multi_object: v })}
          disabled={disabled}
        />
        {params.multi_object && (
          <SliderRow
            label="Max objects"
            value={params.max_objects}
            min={1}
            max={25}
            onChange={(v) => onChange({ max_objects: v })}
            disabled={disabled}
          />
        )}
      </Section>

      <Section title="Output">
        <label className="block">
          <span className="mb-1 block text-xs text-slate-600">Shape type</span>
          <select
            value={params.shape_type}
            disabled={disabled}
            onChange={(e) => onChange({ shape_type: e.target.value as "path" | "polygon" })}
            className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm disabled:opacity-40"
          >
            <option value="path">&lt;path&gt;</option>
            <option value="polygon">&lt;polygon&gt;</option>
          </select>
        </label>
        <div className="flex items-center justify-between text-xs text-slate-600">
          <span>Stroke color</span>
          <input
            type="color"
            value={params.stroke_color}
            disabled={disabled}
            onChange={(e) => onChange({ stroke_color: e.target.value })}
            className="h-7 w-10 cursor-pointer rounded border border-slate-300"
          />
        </div>
        <SliderRow
          label="Stroke width"
          value={params.stroke_width}
          min={0.5}
          max={10}
          step={0.5}
          onChange={(v) => onChange({ stroke_width: v })}
          disabled={disabled}
        />
      </Section>
    </div>
  );
}
