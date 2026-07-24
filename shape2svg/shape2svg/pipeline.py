"""Orchestrator: image in -> geometry + SVG out. No per-image logic anywhere."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

from shape2svg import preprocess as prep
from shape2svg.autodetect import ModeDecision, analyze
from shape2svg.lines import Polyline, extract_lines
from shape2svg.regions import Region, extract_regions
from shape2svg.svg_out import build_json, build_svg


@dataclass
class PipelineConfig:
    mode: str = "auto"                 # auto | regions | lines
    max_dim: int = 1200                # processing resolution (output coords stay original-res)
    blur_kernel: Optional[int] = None  # None = auto from image statistics
    use_clahe: bool = False
    bilateral: bool = False
    # region mode
    threshold_mode: str = "otsu"       # otsu | adaptive
    invert: Optional[bool] = None      # None = auto polarity
    morph_kernel: int = 5
    min_area_ratio: float = 0.005
    max_regions: int = 8
    epsilon_frac: float = 0.005
    use_hull: bool = False
    include_holes: bool = True
    # line mode
    line_source: str = "auto"          # auto | canny | threshold
    merge_kernel: Optional[int] = None      # None = auto
    min_length_frac: Optional[float] = None # None = auto
    line_epsilon_px: float = 2.0
    max_paths: int = 400
    join_segments: bool = True
    join_angle_deg: float = 40.0
    # output
    stroke_width: float = 2.0
    stroke: Optional[str] = None       # None = per-shape palette


@dataclass
class ExtractionResult:
    width: int
    height: int
    mode: str                          # mode actually used
    decision: Optional[ModeDecision]
    regions: List[Region]
    polylines: List[Polyline]
    svg: str
    stats: Dict = field(default_factory=dict)

    @property
    def json(self) -> str:
        return build_json(self.width, self.height, self.mode, self.regions, self.polylines)


def process_image(img_bgr: np.ndarray, config: Optional[PipelineConfig] = None) -> ExtractionResult:
    cfg = config or PipelineConfig()
    H, W = img_bgr.shape[:2]

    needs_analysis = (
        cfg.mode == "auto" or cfg.line_source == "auto"
        or cfg.blur_kernel is None or cfg.merge_kernel is None or cfg.min_length_frac is None
    )
    decision = analyze(img_bgr) if needs_analysis else None
    mode = cfg.mode if cfg.mode != "auto" else decision.mode  # type: ignore[union-attr]

    # data-driven parameter presets: heavier smoothing/merging/filtering for
    # texture-rich photos, gentle settings for clean drawings and shapes
    textured = decision is not None and not decision.near_binary and decision.edge_density > 0.12
    blur_kernel = cfg.blur_kernel if cfg.blur_kernel is not None else (
        3 if (decision is not None and decision.near_binary) else (9 if textured else 5)
    )
    merge_kernel = cfg.merge_kernel if cfg.merge_kernel is not None else (9 if textured else 5)
    min_length_frac = cfg.min_length_frac if cfg.min_length_frac is not None else (0.06 if textured else 0.03)

    small, scale = prep.resize_max_dim(img_bgr, cfg.max_dim)
    gray = prep.to_gray(small, use_clahe=cfg.use_clahe)
    gray_b = prep.denoise(gray, blur_kernel=blur_kernel, bilateral=cfg.bilateral)
    inv_scale = 1.0 / scale

    regions: List[Region] = []
    polylines: List[Polyline] = []

    if mode == "regions":
        binary = prep.binarize(gray_b, mode=cfg.threshold_mode, invert=cfg.invert)
        binary = prep.morph_close(binary, cfg.morph_kernel)
        binary = prep.morph_open(binary, max(3, cfg.morph_kernel // 2))
        regions = [
            r.scaled(inv_scale)
            for r in extract_regions(
                binary,
                min_area_ratio=cfg.min_area_ratio,
                max_regions=cfg.max_regions,
                epsilon_frac=cfg.epsilon_frac,
                use_hull=cfg.use_hull,
                include_holes=cfg.include_holes,
            )
        ]
    else:  # lines
        source_binary = None
        use_threshold = cfg.line_source == "threshold" or (
            cfg.line_source == "auto" and decision is not None and decision.near_binary
        )
        if use_threshold:
            source_binary = prep.binarize(gray_b, mode=cfg.threshold_mode, invert=cfg.invert)
            source_binary = prep.morph_close(source_binary, 3)
        polylines = [
            p.scaled(inv_scale)
            for p in extract_lines(
                gray_b,
                source_binary=source_binary,
                merge_kernel=merge_kernel,
                min_length_frac=min_length_frac,
                epsilon_px=cfg.line_epsilon_px,
                max_paths=cfg.max_paths,
                join=cfg.join_segments,
                join_angle_deg=cfg.join_angle_deg,
            )
        ]

    svg = build_svg(
        W, H, regions=regions, polylines=polylines,
        stroke_width=cfg.stroke_width, stroke=cfg.stroke,
    )
    stats = {
        "image_size": [W, H],
        "processing_scale": round(scale, 4),
        "mode_requested": cfg.mode,
        "mode_used": mode,
        "params_resolved": {
            "blur_kernel": blur_kernel, "merge_kernel": merge_kernel,
            "min_length_frac": min_length_frac, "textured": textured,
        },
        "n_regions": len(regions),
        "n_polylines": len(polylines),
        "total_points": int(
            sum(len(r.points) + sum(len(h) for h in r.holes) for r in regions)
            + sum(len(p.points) for p in polylines)
        ),
    }
    if decision is not None:
        stats["auto_detect"] = {
            "thinness": round(decision.thinness, 4),
            "foreground_frac": round(decision.foreground_frac, 4),
            "near_binary": decision.near_binary,
            "edge_density": round(decision.edge_density, 4),
            "reason": decision.reason,
        }
    return ExtractionResult(W, H, mode, decision, regions, polylines, svg, stats)


def process_file(path: str, config: Optional[PipelineConfig] = None) -> ExtractionResult:
    return process_image(prep.load_image(path), config)


def render_overlay(img_bgr: np.ndarray, result: ExtractionResult, thickness: int = 2) -> np.ndarray:
    """Draw the extracted geometry over the original image (verification aid)."""
    from shape2svg.svg_out import PALETTE

    def bgr(hex_color: str):
        h = hex_color.lstrip("#")
        return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))

    out = img_bgr.copy()
    for i, r in enumerate(result.regions):
        color = bgr(PALETTE[i % len(PALETTE)])
        cv2.polylines(out, [r.points.astype(np.int32)], True, color, thickness, cv2.LINE_AA)
        for hole in r.holes:
            cv2.polylines(out, [hole.astype(np.int32)], True, color, max(1, thickness - 1), cv2.LINE_AA)
    for i, p in enumerate(result.polylines):
        color = bgr(PALETTE[i % len(PALETTE)])
        cv2.polylines(out, [p.points.astype(np.int32)], p.closed, color, thickness, cv2.LINE_AA)
    return out
