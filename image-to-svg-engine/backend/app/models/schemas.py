"""
Pydantic schemas shared by the API layer.

Keeping these separate from the route handlers means the request/response
contract is documented in one place and is automatically reflected in the
FastAPI-generated OpenAPI docs (/docs).
"""
from __future__ import annotations

from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class ProcessingParams(BaseModel):
    """
    Every knob the pipeline exposes. All fields have sane, generic defaults
    so the endpoint works with zero configuration, but a caller (or the
    frontend's control panel) can override any of them per-request.

    Nothing here is tied to a specific image, dataset, or shape category -
    the same parameter set drives railway layouts, floor plans, site
    boundaries, or any other traced outline.
    """

    # Denoising / blur
    blur_kernel: int = Field(
        5, ge=1, le=31, description="Gaussian blur kernel size (odd number, 1 = no blur)."
    )

    # Thresholding
    threshold_mode: Literal["adaptive", "otsu", "binary", "sauvola"] = Field(
        "adaptive",
        description=(
            "Thresholding strategy used to binarize the image. 'sauvola' is a "
            "scikit-image local threshold that handles uneven lighting "
            "particularly well (e.g. aerial/drone photos); it requires the "
            "optional scikit-image dependency to be installed."
        ),
    )
    adaptive_block_size: int = Field(
        35,
        ge=3,
        le=199,
        description="Neighbourhood size (odd number) for 'adaptive' or 'sauvola' threshold modes.",
    )
    adaptive_c: int = Field(
        5, ge=-50, le=50, description="Constant subtracted from the adaptive threshold mean."
    )
    sauvola_k: float = Field(
        0.2, ge=0.01, le=1.0, description="Sauvola threshold sensitivity constant (only used when threshold_mode='sauvola')."
    )
    invert: bool = Field(
        False, description="Invert the binary mask (use when the shape is darker than its background)."
    )

    # Morphology
    morph_kernel: int = Field(
        5, ge=0, le=31, description="Morphological closing kernel size (0 disables closing)."
    )

    # Edge detection
    canny_low: int = Field(50, ge=0, le=500, description="Canny lower threshold.")
    canny_high: int = Field(150, ge=0, le=500, description="Canny upper threshold.")
    auto_canny: bool = Field(
        True, description="Automatically derive Canny thresholds from the image median (recommended)."
    )

    # Contour simplification
    epsilon_factor: float = Field(
        0.01,
        ge=0.0001,
        le=0.2,
        description="Douglas-Peucker epsilon as a fraction of contour perimeter.",
    )
    smoothing: bool = Field(
        False, description="Apply one pass of Chaikin corner-cutting smoothing before simplification."
    )

    # Contour selection
    min_area_ratio: float = Field(
        0.005,
        ge=0.0,
        le=1.0,
        description="Minimum contour area as a fraction of total image area to be considered.",
    )
    multi_object: bool = Field(
        False, description="Detect multiple objects instead of only the single largest contour."
    )
    max_objects: int = Field(1, ge=1, le=25, description="Maximum number of objects to return.")
    use_convex_hull: bool = Field(
        False, description="Replace each contour with its convex hull before simplification."
    )

    # Background removal (bonus)
    remove_background: bool = Field(
        False,
        description="Flood-fill from the image borders to suppress a roughly uniform background before edge detection.",
    )

    # Output
    shape_type: Literal["path", "polygon"] = Field(
        "path", description="Emit SVG <path> or <polygon> elements."
    )
    stroke_color: str = Field("#111827", description="SVG stroke color for the generated shape(s).")
    stroke_width: float = Field(2.0, gt=0, description="SVG stroke width in user units.")
    fill: str = Field("none", description="SVG fill color (e.g. 'none' or a hex color).")


class Point(BaseModel):
    x: float
    y: float


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class DetectedObject(BaseModel):
    """One simplified contour, ready to render or export."""

    id: int
    area: float
    perimeter: float
    raw_point_count: int = Field(..., description="Number of points before simplification.")
    point_count: int = Field(..., description="Number of points after Douglas-Peucker simplification.")
    bounding_box: BoundingBox
    points: List[Point] = Field(..., description="Simplified contour points in original pixel coordinates.")
    points_normalized: List[Point] = Field(
        ..., description="Same points normalized to a 0-1 range using the overall image bounding box."
    )
    points_svg: List[Point] = Field(
        ..., description="Same points in the exact coordinate space used by `svg_path` / the combined `svg` document."
    )
    svg_path: str = Field(..., description="Standalone SVG path 'd' attribute (or polygon 'points') for this object.")


class ImageSize(BaseModel):
    width: int
    height: int


class StagePreviews(BaseModel):
    """Base64 PNG data-URIs for every intermediate pipeline stage, used by the UI's preview tabs."""

    original: str
    grayscale: str
    blurred: str
    threshold: str
    edges: str
    contours_overlay: str


class ProcessingResult(BaseModel):
    success: bool = True
    image_size: ImageSize
    stages: StagePreviews
    objects: List[DetectedObject]
    svg: str = Field(..., description="Combined SVG document containing all detected objects.")
    view_box: str
    params_used: ProcessingParams


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


class SupportedFormats(BaseModel):
    extensions: List[str]
    content_types: List[str]
    max_upload_mb: int
