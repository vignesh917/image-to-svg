"""Region mode: closed-boundary extraction (site outlines, filled shapes, blobs)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import cv2
import numpy as np


@dataclass
class Region:
    """A closed polygon (outer boundary) with optional holes. Pixel coords (x, y)."""
    points: np.ndarray               # (N, 2) float
    holes: List[np.ndarray] = field(default_factory=list)
    area: float = 0.0

    def scaled(self, factor: float) -> "Region":
        return Region(
            points=self.points * factor,
            holes=[h * factor for h in self.holes],
            area=self.area * factor * factor,
        )


def _simplify(contour: np.ndarray, epsilon_frac: float, closed: bool = True) -> np.ndarray:
    peri = cv2.arcLength(contour, closed)
    eps = max(0.5, epsilon_frac * peri)
    approx = cv2.approxPolyDP(contour, eps, closed)
    return approx.reshape(-1, 2).astype(float)


def extract_regions(
    binary: np.ndarray,
    min_area_ratio: float = 0.005,
    max_regions: int = 8,
    epsilon_frac: float = 0.005,
    use_hull: bool = False,
    include_holes: bool = True,
    min_hole_ratio: float = 0.001,
) -> List[Region]:
    """Find contours of the white foreground and simplify them into polygons.

    - min_area_ratio: drop blobs smaller than this fraction of the image area
    - epsilon_frac: Douglas-Peucker tolerance as a fraction of the perimeter
    - include_holes: keep interior holes (rooms in floor plans, courtyards...)
    """
    h, w = binary.shape[:2]
    img_area = float(h * w)
    mode = cv2.RETR_CCOMP if include_holes else cv2.RETR_EXTERNAL
    contours, hierarchy = cv2.findContours(binary, mode, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    hierarchy = hierarchy[0] if hierarchy is not None else None

    regions: List[Region] = []
    for i, cnt in enumerate(contours):
        # top-level contours only (holes are attached below)
        if hierarchy is not None and hierarchy[i][3] != -1:
            continue
        area = cv2.contourArea(cnt)
        if area < min_area_ratio * img_area:
            continue
        if use_hull:
            cnt = cv2.convexHull(cnt)
        pts = _simplify(cnt, epsilon_frac, closed=True)
        if len(pts) < 3:
            continue
        region = Region(points=pts, area=float(area))

        if include_holes and hierarchy is not None and not use_hull:
            child = hierarchy[i][2]
            while child != -1:
                hole_cnt = contours[child]
                if cv2.contourArea(hole_cnt) >= min_hole_ratio * img_area:
                    hole_pts = _simplify(hole_cnt, epsilon_frac, closed=True)
                    if len(hole_pts) >= 3:
                        region.holes.append(hole_pts)
                child = hierarchy[child][0]  # next sibling
        regions.append(region)

    regions.sort(key=lambda r: r.area, reverse=True)
    return regions[:max_regions]
