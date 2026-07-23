/**
 * TypeScript mirror of backend/app/models/schemas.py. Keeping these in
 * sync manually is a deliberate, simple choice for a project this size;
 * see README for the note on generating this automatically from the
 * OpenAPI schema if the API grows.
 */

export type ThresholdMode = "adaptive" | "otsu" | "binary" | "sauvola";
export type ShapeType = "path" | "polygon";

export interface ProcessingParams {
  blur_kernel: number;
  threshold_mode: ThresholdMode;
  adaptive_block_size: number;
  adaptive_c: number;
  sauvola_k: number;
  invert: boolean;
  morph_kernel: number;
  canny_low: number;
  canny_high: number;
  auto_canny: boolean;
  epsilon_factor: number;
  smoothing: boolean;
  min_area_ratio: number;
  multi_object: boolean;
  max_objects: number;
  use_convex_hull: boolean;
  remove_background: boolean;
  shape_type: ShapeType;
  stroke_color: string;
  stroke_width: number;
  fill: string;
}

export const DEFAULT_PARAMS: ProcessingParams = {
  blur_kernel: 5,
  threshold_mode: "adaptive",
  adaptive_block_size: 35,
  adaptive_c: 5,
  sauvola_k: 0.2,
  invert: false,
  morph_kernel: 5,
  canny_low: 50,
  canny_high: 150,
  auto_canny: true,
  epsilon_factor: 0.01,
  smoothing: false,
  min_area_ratio: 0.005,
  multi_object: false,
  max_objects: 1,
  use_convex_hull: false,
  remove_background: false,
  shape_type: "path",
  stroke_color: "#111827",
  stroke_width: 2,
  fill: "none",
};

export interface Point {
  x: number;
  y: number;
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectedObject {
  id: number;
  area: number;
  perimeter: number;
  raw_point_count: number;
  point_count: number;
  bounding_box: BoundingBox;
  points: Point[];
  points_normalized: Point[];
  points_svg: Point[];
  svg_path: string;
}

export interface ImageSize {
  width: number;
  height: number;
}

export interface StagePreviews {
  original: string;
  grayscale: string;
  blurred: string;
  threshold: string;
  edges: string;
  contours_overlay: string;
}

export interface ProcessingResult {
  success: boolean;
  image_size: ImageSize;
  stages: StagePreviews;
  objects: DetectedObject[];
  svg: string;
  view_box: string;
  params_used: ProcessingParams;
}

export interface ApiErrorBody {
  detail?: string;
  error?: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export type StageKey = keyof StagePreviews;

export const STAGE_LABELS: Record<StageKey, string> = {
  original: "Original",
  grayscale: "Grayscale",
  blurred: "Blurred",
  threshold: "Threshold",
  edges: "Edges",
  contours_overlay: "Contours",
};
