"""
Stage 5-6 of the pipeline: contour detection, selection, and simplification.

This module is the heart of the "no manual tracing, no hardcoded
coordinates" requirement - every coordinate that leaves this module was
computed from the pixels that were actually uploaded, via general-purpose
OpenCV geometry functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import cv2
import numpy as np


@dataclass
class RawContour:
    points: np.ndarray  # (N, 2) float32, original pixel coordinates
    area: float
    perimeter: float


def find_all_contours(binary: np.ndarray) -> List[np.ndarray]:
    """
    Find external contours in a binary/edge image.

    RETR_EXTERNAL is intentional: for boundary/outline extraction (site
    boundary, building outline, layout perimeter) we want the outermost
    silhouette of each object, not every nested hole or internal edge.
    """
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return contours


def select_significant_contours(
    contours: List[np.ndarray],
    image_area: float,
    min_area_ratio: float,
    max_objects: int,
    max_area_ratio: float = 0.97,
) -> List[RawContour]:
    """
    Filter out noise (contours smaller than `min_area_ratio` of the image)
    and keep the `max_objects` largest remaining contours, sorted by area
    descending. This generalizes "largest contour extraction" to an
    optional "N largest objects" for multi-object scenes.

    `max_area_ratio` guards against a well-known OpenCV edge case: when a
    binary mask has no internal boundary at all (e.g. a blank/uniform
    image, or a mask that touches every border), `findContours` can return
    the image's own outer frame as a single "contour". That carries no
    real shape information, so it is treated the same as "nothing found"
    rather than returned as a false-positive rectangle.
    """
    candidates: List[RawContour] = []
    min_area = image_area * min_area_ratio
    max_area = image_area * max_area_ratio

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        perimeter = cv2.arcLength(c, True)
        pts = c.reshape(-1, 2).astype(np.float32)
        candidates.append(RawContour(points=pts, area=area, perimeter=perimeter))

    candidates.sort(key=lambda rc: rc.area, reverse=True)
    return candidates[:max_objects]


def to_convex_hull(points: np.ndarray) -> np.ndarray:
    """Replace a point set with its convex hull. Useful for boundary-style
    shapes (site/plot boundaries) that should be a clean envelope rather
    than following every concave nook in the detected edge."""
    hull = cv2.convexHull(points.reshape(-1, 1, 2).astype(np.float32))
    return hull.reshape(-1, 2)


def chaikin_smooth(points: np.ndarray, iterations: int = 1) -> np.ndarray:
    """
    Chaikin's corner-cutting algorithm: a cheap, dependency-free way to
    smooth a polyline before simplification. Operates on a closed polygon.
    """
    pts = points
    for _ in range(max(1, iterations)):
        if len(pts) < 3:
            break
        new_pts = []
        n = len(pts)
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            q = 0.75 * p0 + 0.25 * p1
            r = 0.25 * p0 + 0.75 * p1
            new_pts.append(q)
            new_pts.append(r)
        pts = np.array(new_pts, dtype=np.float32)
    return pts


def douglas_peucker(points: np.ndarray, epsilon_factor: float, perimeter: float) -> np.ndarray:
    """
    Ramer-Douglas-Peucker polygon simplification via cv2.approxPolyDP.

    `epsilon_factor` is expressed as a fraction of the contour's own
    perimeter (not an absolute pixel count), so the same default works for
    a 400px thumbnail and a 6000px drone photo alike.
    """
    epsilon = max(epsilon_factor * perimeter, 0.1)
    contour_cv = points.reshape(-1, 1, 2).astype(np.float32)
    approx = cv2.approxPolyDP(contour_cv, epsilon, closed=True)
    return approx.reshape(-1, 2)
