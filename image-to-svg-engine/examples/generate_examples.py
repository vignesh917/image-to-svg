#!/usr/bin/env python3
"""
Generates one synthetic sample image per shape category named in the spec
(site boundary, railway layout, floor plan, building outline, road layout,
generic polygon), then runs the SAME engine used by the API
(`app.opencv_pipeline.pipeline.process_image` - zero code duplication) on
each to produce example .svg/.json outputs.

Run from the repository root:

    python3 examples/generate_examples.py

This exists to (a) prove the engine generalizes across shape categories
without any per-image code, and (b) give reviewers ready-made before/after
material without needing their own source images.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / ".pydeps"))  # picks up locally-vendored deps if present

from app.opencv_pipeline.pipeline import PipelineConfig, process_image  # noqa: E402

INPUT_DIR = REPO_ROOT / "examples" / "input"
OUTPUT_DIR = REPO_ROOT / "examples" / "output"


def _add_texture(canvas: np.ndarray, rng: np.random.Generator, amount: int = 10) -> np.ndarray:
    """Light speckle noise so synthetic images aren't perfectly flat - closer
    to a real scan/photo and a fairer test of the thresholding stage."""
    noise = rng.integers(-amount, amount, canvas.shape, endpoint=True)
    noisy = np.clip(canvas.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return noisy


def make_site_boundary(rng: np.random.Generator) -> np.ndarray:
    """An irregular property/site boundary over a mottled terrain-like backdrop."""
    size = 640
    canvas = np.full((size, size, 3), 205, dtype=np.uint8)
    for _ in range(40):
        cx, cy = rng.integers(0, size, 2)
        r = rng.integers(15, 45)
        shade = int(rng.integers(170, 220))
        cv2.circle(canvas, (cx, cy), r, (shade, shade, shade), -1)
    canvas = _add_texture(canvas, rng, 8)

    pts = np.array(
        [[120, 90], [430, 60], [560, 200], [520, 420], [300, 560], [130, 480], [70, 260]],
        np.int32,
    )
    cv2.polylines(canvas, [pts], isClosed=True, color=(20, 20, 20), thickness=5)
    return canvas


def make_railway_layout(rng: np.random.Generator) -> np.ndarray:
    """A yard boundary (slightly trapezoidal, like a perspective aerial shot)
    with internal parallel track lines and ballast texture - the outer
    boundary is the target contour, exactly like the sample rail-yard
    photos this engine is designed for."""
    size = 640
    canvas = np.full((size, size, 3), 190, dtype=np.uint8)
    canvas = _add_texture(canvas, rng, 12)

    boundary = np.array([[60, 140], [580, 90], [610, 480], [40, 520]], np.int32)
    cv2.polylines(canvas, [boundary], isClosed=True, color=(15, 15, 15), thickness=6)

    # Internal texture: several near-parallel track lines: clutter that a
    # real boundary-extraction pipeline must see past.
    for i in range(7):
        y0 = 160 + i * 45
        y1 = 130 + i * 48
        cv2.line(canvas, (90, y0), (560, y1), (60, 60, 60), 2)
    return canvas


def make_floor_plan(rng: np.random.Generator) -> np.ndarray:
    """A clean, CAD-style L-shaped building footprint on white - flat
    lighting, thin crisp lines (closer to a scanned plan than a photo)."""
    size = 640
    canvas = np.full((size, size, 3), 255, dtype=np.uint8)
    canvas = _add_texture(canvas, rng, 3)

    pts = np.array(
        [[100, 100], [400, 100], [400, 260], [520, 260], [520, 520], [100, 520]],
        np.int32,
    )
    cv2.polylines(canvas, [pts], isClosed=True, color=(10, 10, 10), thickness=3)
    return canvas


def make_building_outline(rng: np.random.Generator) -> np.ndarray:
    """A rotated hexagonal building footprint over a satellite-photo-like
    mottled background - directly exercises rotation/angle preservation."""
    size = 640
    canvas = np.full((size, size, 3), 160, dtype=np.uint8)
    for _ in range(30):
        cx, cy = rng.integers(0, size, 2)
        r = rng.integers(20, 60)
        shade = int(rng.integers(100, 190))
        cv2.circle(canvas, (cx, cy), r, (shade, shade, shade), -1)
    canvas = _add_texture(canvas, rng, 10)

    center = (size // 2, size // 2)
    radius = 220
    angle_offset = 27  # degrees - deliberately not axis-aligned
    hexagon = []
    for i in range(6):
        theta = math.radians(60 * i + angle_offset)
        hexagon.append((center[0] + radius * math.cos(theta), center[1] + radius * math.sin(theta)))
    hexagon = np.array(hexagon, np.int32)
    cv2.polylines(canvas, [hexagon], isClosed=True, color=(25, 25, 25), thickness=5)
    return canvas


def make_road_layout(rng: np.random.Generator) -> np.ndarray:
    """A closed road/loop boundary (rounded rectangle) over an asphalt-like
    textured background."""
    size = 640
    canvas = np.full((size, size, 3), 130, dtype=np.uint8)
    canvas = _add_texture(canvas, rng, 14)

    overlay = canvas.copy()
    cv2.rectangle(overlay, (110, 160), (530, 480), (235, 235, 235), -1)
    cv2.addWeighted(overlay, 0.0, canvas, 1.0, 0, canvas)  # placeholder blend (kept 0 to preserve texture)
    cv2.rectangle(canvas, (110, 160), (530, 480), (20, 20, 20), 6)
    return canvas


def make_generic_polygon(rng: np.random.Generator) -> np.ndarray:
    """A rotated 5-pointed star-adjacent convex pentagon - a plain
    'polygon shape' example decoupled from any real-world category."""
    size = 640
    canvas = np.full((size, size, 3), 245, dtype=np.uint8)
    canvas = _add_texture(canvas, rng, 4)

    center = (size // 2, size // 2)
    radius = 230
    angle_offset = 12
    pentagon = []
    for i in range(5):
        theta = math.radians(72 * i + angle_offset)
        pentagon.append((center[0] + radius * math.cos(theta), center[1] + radius * math.sin(theta)))
    pentagon = np.array(pentagon, np.int32)
    cv2.polylines(canvas, [pentagon], isClosed=True, color=(30, 30, 30), thickness=4)
    return canvas


GENERATORS = {
    "site_boundary": (make_site_boundary, PipelineConfig(threshold_mode="otsu", epsilon_factor=0.012)),
    "railway_layout": (
        make_railway_layout,
        PipelineConfig(threshold_mode="sauvola", blur_kernel=7, morph_kernel=9, epsilon_factor=0.01),
    ),
    "floor_plan": (make_floor_plan, PipelineConfig(threshold_mode="otsu", blur_kernel=3, epsilon_factor=0.006)),
    "building_outline": (
        make_building_outline,
        PipelineConfig(threshold_mode="otsu", epsilon_factor=0.01, use_convex_hull=True),
    ),
    "road_layout": (make_road_layout, PipelineConfig(threshold_mode="otsu", epsilon_factor=0.01)),
    "generic_polygon": (make_generic_polygon, PipelineConfig(threshold_mode="otsu", epsilon_factor=0.01)),
}


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    for name, (generator, config) in GENERATORS.items():
        image = generator(rng)
        input_path = INPUT_DIR / f"{name}.png"
        cv2.imwrite(str(input_path), image)

        result = process_image(image, config)

        svg_path = OUTPUT_DIR / f"{name}.svg"
        svg_path.write_text(result.svg)

        overlay_path = OUTPUT_DIR / f"{name}_contours.png"
        cv2.imwrite(str(overlay_path), result.stage_images["contours_overlay"])

        payload = {
            "image_size": {"width": result.width, "height": result.height},
            "view_box": f"0 0 {result.view_box.width:.2f} {result.view_box.height:.2f}",
            "objects": [
                {
                    "id": obj.id,
                    "area": obj.area,
                    "perimeter": obj.perimeter,
                    "raw_point_count": obj.raw_point_count,
                    "point_count": obj.point_count,
                    "bounding_box": vars(obj.bounding_box),
                    "points": obj.points.tolist(),
                    "points_normalized": obj.points_normalized.tolist(),
                }
                for obj in result.objects
            ],
        }
        json_path = OUTPUT_DIR / f"{name}.json"
        json_path.write_text(json.dumps(payload, indent=2))

        print(f"{name:18s} -> {len(result.objects)} object(s), "
              f"{result.objects[0].point_count} points | wrote {svg_path.name}, {json_path.name}, {overlay_path.name}")


if __name__ == "__main__":
    main()
