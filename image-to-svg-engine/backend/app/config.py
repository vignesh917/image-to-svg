"""
Application configuration.

All limits and defaults live here so behaviour can be tuned via environment
variables without touching any processing code. Nothing in this module is
specific to any one image, shape, or dataset - that is the whole point of
the engine: the same code path handles a railway layout today and a floor
plan tomorrow.
"""
from __future__ import annotations

import os
from typing import List


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """Central, environment-overridable settings object."""

    # --- Server -------------------------------------------------------
    APP_NAME: str = "Image-to-SVG Extraction Engine"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = _env_list(
        "CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- Upload constraints --------------------------------------------
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    SUPPORTED_CONTENT_TYPES: List[str] = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/x-tiff",
    ]
    SUPPORTED_EXTENSIONS: List[str] = [
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
    ]

    # --- Default pipeline parameters ------------------------------------
    # These are safe, general-purpose defaults. Every one of them is also
    # exposed to the API/UI so a user can tune behaviour per-image without
    # ever touching source code.
    DEFAULT_BLUR_KERNEL: int = 5
    DEFAULT_ADAPTIVE_BLOCK_SIZE: int = 35
    DEFAULT_ADAPTIVE_C: int = 5
    DEFAULT_CANNY_LOW: int = 50
    DEFAULT_CANNY_HIGH: int = 150
    DEFAULT_MORPH_KERNEL: int = 5
    DEFAULT_EPSILON_FACTOR: float = 0.01
    DEFAULT_MIN_AREA_RATIO: float = 0.005  # 0.5% of image area
    DEFAULT_MAX_OBJECTS: int = 1
    MAX_ALLOWED_OBJECTS: int = 25


settings = Settings()
