"""
Stage 7 of the pipeline: bounding box + coordinate normalization.

Design decision (important for correctness): we never scale, rotate, or
otherwise distort coordinates relative to each other. We only ever
translate points (subtract an origin) and, for the *normalized* variant,
divide every point by the same single scalar. Because a single uniform
scale factor is applied equally to x and y, angles, aspect ratio, and
relative proportions are mathematically preserved. This is what satisfies
the "preserve shape / angles / scale / aspect ratio / orientation"
requirement, generically, for any input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


def bounding_box_of(points: np.ndarray) -> BoundingBox:
    x_min, y_min = points[:, 0].min(), points[:, 1].min()
    x_max, y_max = points[:, 0].max(), points[:, 1].max()
    return BoundingBox(x=float(x_min), y=float(y_min),
                        width=float(x_max - x_min), height=float(y_max - y_min))


def union_bounding_box(boxes: List[BoundingBox]) -> BoundingBox:
    x_min = min(b.x for b in boxes)
    y_min = min(b.y for b in boxes)
    x_max = max(b.x + b.width for b in boxes)
    y_max = max(b.y + b.height for b in boxes)
    return BoundingBox(x=x_min, y=y_min, width=x_max - x_min, height=y_max - y_min)


def normalize_unit(points: np.ndarray, reference_box: BoundingBox) -> np.ndarray:
    """
    Map points into a 0..1 range using ONE scalar (the larger side of the
    reference bounding box) so x and y are scaled identically. This keeps
    aspect ratio exact; it deliberately does NOT stretch width/height
    independently to fill a unit square (that would distort the shape).
    """
    scale = max(reference_box.width, reference_box.height) or 1.0
    out = points.copy().astype(np.float64)
    out[:, 0] = (out[:, 0] - reference_box.x) / scale
    out[:, 1] = (out[:, 1] - reference_box.y) / scale
    return out


def translate_to_origin(points: np.ndarray, reference_box: BoundingBox, padding: float = 0.0) -> np.ndarray:
    """Shift points so the reference bounding box's top-left lands at
    (padding, padding). Pure translation - no scaling, no rotation."""
    out = points.copy().astype(np.float64)
    out[:, 0] = out[:, 0] - reference_box.x + padding
    out[:, 1] = out[:, 1] - reference_box.y + padding
    return out
