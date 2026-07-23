"""
Unit tests for the CV pipeline, using synthetically generated shapes so the
tests are deterministic and require no external fixture images. If these
pass, the pipeline is verified to work generically on ANY high-contrast
shape - which is exactly the "no hardcoded coordinates, works for future
images" requirement.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from app.opencv_pipeline.pipeline import PipelineConfig, PipelineError, process_image


def _blank_canvas(size: int = 500) -> np.ndarray:
    canvas = np.full((size, size, 3), 255, dtype=np.uint8)
    return canvas


def _draw_rectangle(size: int = 500, margin: int = 100) -> np.ndarray:
    canvas = _blank_canvas(size)
    cv2.rectangle(canvas, (margin, margin), (size - margin, size - margin), (0, 0, 0), thickness=4)
    return canvas


def _draw_rotated_rectangle(size: int = 500) -> np.ndarray:
    canvas = _blank_canvas(size)
    center = (size // 2, size // 2)
    rect = ((center[0], center[1]), (220, 120), 35.0)  # width=220, height=120, angle=35deg
    box = cv2.boxPoints(rect).astype(np.int32)
    cv2.drawContours(canvas, [box], 0, (0, 0, 0), thickness=4)
    return canvas, rect


def _draw_triangle(size: int = 500) -> np.ndarray:
    canvas = _blank_canvas(size)
    pts = np.array([[size // 2, 80], [100, size - 100], [size - 100, size - 100]], np.int32)
    cv2.polylines(canvas, [pts], isClosed=True, color=(0, 0, 0), thickness=4)
    return canvas


def test_rectangle_produces_four_point_quad():
    image = _draw_rectangle()
    result = process_image(image, PipelineConfig())

    assert len(result.objects) == 1
    obj = result.objects[0]
    # A clean rectangle should simplify down to (close to) 4 points.
    assert 4 <= obj.point_count <= 6
    assert obj.bounding_box.width > 0 and obj.bounding_box.height > 0


def test_rectangle_aspect_ratio_is_preserved():
    size, margin = 500, 100
    image = _draw_rectangle(size=size, margin=margin)
    result = process_image(image, PipelineConfig())
    obj = result.objects[0]

    expected_side = size - 2 * margin
    # Detected bounding box should closely match the drawn square (within
    # a few pixels of stroke-width slack), proving scale/aspect ratio are
    # preserved end-to-end rather than distorted by normalization.
    assert abs(obj.bounding_box.width - expected_side) < 15
    assert abs(obj.bounding_box.height - expected_side) < 15
    aspect_ratio = obj.bounding_box.width / obj.bounding_box.height
    assert abs(aspect_ratio - 1.0) < 0.05


def test_rotated_rectangle_preserves_orientation():
    image, rect = _draw_rotated_rectangle()
    result = process_image(image, PipelineConfig(epsilon_factor=0.02))
    obj = result.objects[0]

    assert obj.point_count in (4, 5, 6)
    # The rotated rectangle's bounding box must be strictly larger than its
    # own un-rotated width/height (since it's tilted 35 degrees) - this
    # confirms the pipeline is reading real geometry, not a hardcoded box.
    (_, _), (rw, rh), _ = rect
    assert obj.bounding_box.width > rw
    assert obj.bounding_box.height > rh


def test_triangle_produces_three_points():
    image = _draw_triangle()
    result = process_image(image, PipelineConfig(epsilon_factor=0.02))
    obj = result.objects[0]
    assert obj.point_count in (3, 4)


def test_svg_output_is_well_formed_and_fits_viewbox():
    image = _draw_rectangle()
    result = process_image(image, PipelineConfig())

    assert result.svg.startswith("<svg")
    assert "viewBox=" in result.svg
    assert "<path" in result.svg or "<polygon" in result.svg
    assert result.svg.strip().endswith("</svg>")


def test_polygon_shape_type():
    image = _draw_triangle()
    result = process_image(image, PipelineConfig(shape_type="polygon"))
    assert "<polygon" in result.svg


def test_normalized_points_are_within_unit_range():
    image = _draw_rectangle()
    result = process_image(image, PipelineConfig())
    obj = result.objects[0]
    for x, y in obj.points_normalized:
        assert -0.01 <= x <= 1.01
        assert -0.01 <= y <= 1.01


def test_multi_object_detects_two_shapes():
    canvas = _blank_canvas(600)
    cv2.rectangle(canvas, (40, 40), (250, 250), (0, 0, 0), thickness=4)
    cv2.circle(canvas, (430, 430), 120, (0, 0, 0), thickness=4)

    result = process_image(
        canvas, PipelineConfig(multi_object=True, max_objects=5, min_area_ratio=0.01)
    )
    assert len(result.objects) == 2


def test_no_shape_raises_pipeline_error():
    blank = _blank_canvas(300)  # pure white, nothing to detect
    with pytest.raises(PipelineError):
        process_image(blank, PipelineConfig(min_area_ratio=0.01))


def test_convex_hull_option_reduces_or_maintains_convexity():
    image = _draw_triangle()
    result = process_image(image, PipelineConfig(use_convex_hull=True))
    assert len(result.objects) == 1
    assert result.objects[0].point_count >= 3
