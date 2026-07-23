"""
Stage 8 of the pipeline: SVG generation.

Generates SVG natively (plain string building) rather than depending on a
third-party SVG library - the output format is simple enough (a handful of
<path>/<polygon> elements inside an auto-fitted <svg>) that hand-rolling it
keeps the dependency surface small and the output fully predictable/testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal

import numpy as np

from app.opencv_pipeline.normalize import BoundingBox

# A small, readable palette used only when multiple objects are detected, so
# each object is visually distinguishable in the combined preview SVG.
_PALETTE = [
    "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed",
    "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5",
]


@dataclass
class SvgObject:
    points: np.ndarray  # points already translated into SVG coordinate space
    stroke: str
    fill: str
    stroke_width: float
    shape_type: Literal["path", "polygon"] = "path"


def _format_number(value: float) -> str:
    """Round to 2 decimal places and strip a trailing '.00' for compactness."""
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def points_to_path_d(points: np.ndarray) -> str:
    """Build an SVG path 'd' attribute: M x,y L x,y L x,y ... Z"""
    if len(points) == 0:
        return ""
    parts = [f"M{_format_number(points[0][0])},{_format_number(points[0][1])}"]
    for p in points[1:]:
        parts.append(f"L{_format_number(p[0])},{_format_number(p[1])}")
    parts.append("Z")
    return " ".join(parts)


def points_to_polygon_points(points: np.ndarray) -> str:
    """Build an SVG <polygon> 'points' attribute: 'x,y x,y x,y ...'"""
    return " ".join(f"{_format_number(p[0])},{_format_number(p[1])}" for p in points)


def object_svg_fragment(obj: SvgObject) -> str:
    """Return the standalone <path>/<polygon> markup for a single object
    (used both inside the combined document and for per-object exports)."""
    if obj.shape_type == "polygon":
        pts = points_to_polygon_points(obj.points)
        return (f'<polygon points="{pts}" fill="{obj.fill}" '
                f'stroke="{obj.stroke}" stroke-width="{obj.stroke_width}" '
                f'stroke-linejoin="round" />')
    d = points_to_path_d(obj.points)
    return (f'<path d="{d}" fill="{obj.fill}" stroke="{obj.stroke}" '
            f'stroke-width="{obj.stroke_width}" stroke-linejoin="round" />')


def build_svg_document(
    objects: List[SvgObject],
    view_box: BoundingBox,
    title: str = "Extracted contour",
) -> str:
    """
    Wrap one or more shape fragments in a complete, self-contained <svg>
    document whose viewBox exactly matches the (padded) bounding box of the
    detected geometry, so the shape automatically fills the viewport at any
    render size with correct aspect ratio.
    """
    width = max(view_box.width, 1)
    height = max(view_box.height, 1)
    fragments = "\n  ".join(object_svg_fragment(o) for o in objects)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_format_number(width)} {_format_number(height)}" '
        f'width="{_format_number(width)}" height="{_format_number(height)}" '
        f'role="img" aria-label="{title}">\n'
        f"  <title>{title}</title>\n"
        f"  {fragments}\n"
        f"</svg>"
    )


def color_for_index(index: int) -> str:
    return _PALETTE[index % len(_PALETTE)]
