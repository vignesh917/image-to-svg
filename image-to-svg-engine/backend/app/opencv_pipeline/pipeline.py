"""
The orchestrator: wires every stage together into one `process_image` call.

`PipelineConfig` is a plain dataclass (no pydantic/FastAPI dependency) so
this entire package can be imported and used standalone - as a CLI, in a
notebook, or from a completely different web framework - which is the
point of calling it a reusable "engine" rather than a demo endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

import cv2
import numpy as np

from app.opencv_pipeline import contours as contour_ops
from app.opencv_pipeline import edges as edge_ops
from app.opencv_pipeline import preprocessing as prep
from app.opencv_pipeline.normalize import (
    BoundingBox,
    bounding_box_of,
    normalize_unit,
    translate_to_origin,
    union_bounding_box,
)
from app.svg.generator import SvgObject, build_svg_document, color_for_index, object_svg_fragment


class PipelineError(Exception):
    """Raised when no usable boundary can be found for the given parameters."""


@dataclass
class PipelineConfig:
    blur_kernel: int = 5
    threshold_mode: Literal["adaptive", "otsu", "binary", "sauvola"] = "adaptive"
    adaptive_block_size: int = 35
    adaptive_c: int = 5
    sauvola_k: float = 0.2
    invert: bool = False
    morph_kernel: int = 5
    canny_low: int = 50
    canny_high: int = 150
    auto_canny: bool = True
    epsilon_factor: float = 0.01
    smoothing: bool = False
    min_area_ratio: float = 0.005
    multi_object: bool = False
    max_objects: int = 1
    use_convex_hull: bool = False
    remove_background: bool = False
    shape_type: Literal["path", "polygon"] = "path"
    stroke_color: str = "#111827"
    stroke_width: float = 2.0
    fill: str = "none"


@dataclass
class DetectedObjectResult:
    id: int
    area: float
    perimeter: float
    raw_point_count: int
    point_count: int
    bounding_box: BoundingBox
    points: np.ndarray            # simplified, original pixel coordinates
    points_normalized: np.ndarray  # simplified, normalized 0..1 coordinates
    points_svg: np.ndarray         # simplified, in the same coordinate space as `svg_fragment`
    svg_fragment: str


@dataclass
class PipelineResult:
    width: int
    height: int
    stage_images: dict            # name -> np.ndarray (grayscale or BGR)
    objects: List[DetectedObjectResult]
    svg: str
    view_box: BoundingBox


def _build_binary_mask(gray_blurred: np.ndarray, config: PipelineConfig) -> np.ndarray:
    if config.threshold_mode == "adaptive":
        return prep.adaptive_threshold(
            gray_blurred, config.adaptive_block_size, config.adaptive_c, config.invert
        )
    if config.threshold_mode == "otsu":
        return prep.otsu_threshold(gray_blurred, config.invert)
    if config.threshold_mode == "sauvola":
        return prep.sauvola_threshold(
            gray_blurred, config.adaptive_block_size, config.sauvola_k, config.invert
        )
    return prep.binary_threshold(gray_blurred, config.invert)


def _contours_from_binary(binary: np.ndarray, config: PipelineConfig) -> tuple[np.ndarray, list]:
    """Canny -> morphological closing -> findContours, per the documented
    pipeline. Returns (edge_map, raw_contours)."""
    if config.auto_canny:
        low, high = edge_ops.auto_canny_thresholds(binary)
    else:
        low, high = config.canny_low, config.canny_high

    edges = edge_ops.canny_edges(binary, low, high)
    closed = prep.morphological_closing(edges, config.morph_kernel)
    raw_contours = contour_ops.find_all_contours(closed)
    return closed, raw_contours


def process_image(image_bgr: np.ndarray, config: PipelineConfig) -> PipelineResult:
    """
    Run the full image -> SVG pipeline and return every intermediate stage
    plus the final geometry/SVG. Raises `PipelineError` if, even after
    fallbacks, no contour satisfies `min_area_ratio` - this is preferred
    over silently returning an empty/garbage shape.
    """
    h, w = image_bgr.shape[:2]
    image_area = float(h * w)

    # --- Stage 1: grayscale -------------------------------------------------
    gray = prep.to_grayscale(image_bgr)

    # --- Optional bonus stage: background suppression -----------------------
    working_gray = gray
    if config.remove_background:
        fg_mask = prep.remove_background(gray)
        working_gray = cv2.bitwise_and(gray, fg_mask)

    # --- Stage 2: denoise + Gaussian blur ------------------------------------
    denoised = prep.denoise(working_gray) if min(h, w) <= 2000 else working_gray
    blurred = prep.gaussian_blur(denoised, config.blur_kernel)

    # --- Stage 3: threshold -> binary image ----------------------------------
    binary = _build_binary_mask(blurred, config)
    binary = prep.morphological_open(binary, max(config.morph_kernel - 2, 0))

    # --- Stage 4-5: Canny edges -> morphological closing -> find contours ----
    edge_map, raw_contours = _contours_from_binary(binary, config)

    # --- Stage 6: select significant contour(s) with graceful fallbacks -----
    max_objects = config.max_objects if config.multi_object else 1
    selected = contour_ops.select_significant_contours(
        raw_contours, image_area, config.min_area_ratio, max_objects
    )

    if not selected:
        # Fallback 1: try Otsu instead of the configured mode (handles
        # unusually flat or unusually noisy lighting the user didn't expect).
        fallback_binary = prep.otsu_threshold(blurred, config.invert)
        edge_map, raw_contours = _contours_from_binary(fallback_binary, config)
        selected = contour_ops.select_significant_contours(
            raw_contours, image_area, config.min_area_ratio, max_objects
        )

    if not selected:
        # Fallback 2: find contours directly on the binary mask itself,
        # skipping Canny entirely - robust when the mask boundary is clean
        # but doesn't survive edge detection well (e.g. near-uniform fill).
        raw_contours = contour_ops.find_all_contours(binary)
        selected = contour_ops.select_significant_contours(
            raw_contours, image_area, config.min_area_ratio, max_objects
        )

    if not selected:
        raise PipelineError(
            "No boundary could be detected with the current parameters. "
            "Try lowering 'min area ratio', enabling 'invert', or switching "
            "threshold mode."
        )

    # --- Stage 7: simplify + normalize each selected contour -----------------
    all_boxes: List[BoundingBox] = []
    interim = []
    for raw in selected:
        pts = raw.points
        if config.use_convex_hull:
            pts = contour_ops.to_convex_hull(pts)
        if config.smoothing:
            pts = contour_ops.chaikin_smooth(pts, iterations=1)
        simplified = contour_ops.douglas_peucker(pts, config.epsilon_factor, raw.perimeter)
        if len(simplified) < 3:
            # Degenerate result (a line/point) - fall back to the
            # un-simplified point set rather than emitting a broken shape.
            simplified = pts
        box = bounding_box_of(simplified)
        all_boxes.append(box)
        interim.append((raw, simplified, box))

    view_box = union_bounding_box(all_boxes)
    padding = max(view_box.width, view_box.height) * 0.02

    objects: List[DetectedObjectResult] = []
    svg_objects: List[SvgObject] = []
    for idx, (raw, simplified, box) in enumerate(interim):
        svg_space_points = translate_to_origin(simplified, view_box, padding=padding)
        normalized_points = normalize_unit(simplified, view_box)

        stroke = config.stroke_color if len(interim) == 1 else color_for_index(idx)
        svg_obj = SvgObject(
            points=svg_space_points,
            stroke=stroke,
            fill=config.fill,
            stroke_width=config.stroke_width,
            shape_type=config.shape_type,
        )
        svg_objects.append(svg_obj)

        objects.append(
            DetectedObjectResult(
                id=idx,
                area=float(raw.area),
                perimeter=float(raw.perimeter),
                raw_point_count=int(len(raw.points)),
                point_count=int(len(simplified)),
                bounding_box=box,
                points=simplified,
                points_normalized=normalized_points,
                points_svg=svg_space_points,
                svg_fragment=object_svg_fragment(svg_obj),
            )
        )

    padded_view_box = BoundingBox(
        x=0, y=0, width=view_box.width + 2 * padding, height=view_box.height + 2 * padding
    )
    svg_document = build_svg_document(svg_objects, padded_view_box)

    # --- Visual debug stages for the UI's preview tabs -----------------------
    contours_overlay = image_bgr.copy()
    for idx, (_, simplified, _) in enumerate(interim):
        color_hex = config.stroke_color if len(interim) == 1 else color_for_index(idx)
        color_bgr = _hex_to_bgr(color_hex)
        pts_int = simplified.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(contours_overlay, [pts_int], isClosed=True, color=color_bgr, thickness=3)
        for p in simplified.astype(np.int32):
            cv2.circle(contours_overlay, tuple(p), 5, color_bgr, -1)
            cv2.circle(contours_overlay, tuple(p), 5, (255, 255, 255), 1)

    stage_images = {
        "original": image_bgr,
        "grayscale": gray,
        "blurred": blurred,
        "threshold": binary,
        "edges": edge_map,
        "contours_overlay": contours_overlay,
    }

    return PipelineResult(
        width=w,
        height=h,
        stage_images=stage_images,
        objects=objects,
        svg=svg_document,
        view_box=padded_view_box,
    )


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (17, 24, 39)  # default slate-900-ish
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)
