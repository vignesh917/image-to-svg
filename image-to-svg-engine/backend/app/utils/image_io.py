"""
Format-agnostic image I/O helpers.

Uses Pillow (not cv2.imdecode directly) to decode the incoming bytes because
Pillow's format support is broader and more forgiving (PNG/JPEG/WEBP/BMP/TIFF,
including palette, CMYK, and multi-page TIFF edge cases). The result is
always normalized to a standard 3-channel BGR uint8 numpy array, which is
the one shape every downstream OpenCV function can rely on - this is what
lets the rest of the pipeline stay completely format-agnostic.
"""
from __future__ import annotations

import base64
import io
from typing import Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps


class UnsupportedImageError(ValueError):
    """Raised when the uploaded bytes cannot be decoded as an image."""


def decode_image(raw_bytes: bytes) -> np.ndarray:
    """
    Decode arbitrary image bytes (PNG/JPEG/WEBP/BMP/TIFF/...) into a BGR
    uint8 numpy array, the canonical format used throughout the pipeline.
    """
    try:
        with Image.open(io.BytesIO(raw_bytes)) as pil_image:
            # Respect EXIF orientation (common in phone/drone photos) so the
            # detected contour matches what a human sees, not the raw sensor
            # orientation.
            pil_image = ImageOps.exif_transpose(pil_image)
            pil_image = pil_image.convert("RGB")
            rgb = np.array(pil_image)
    except Exception as exc:  # noqa: BLE001 - we re-raise as our own type
        raise UnsupportedImageError(f"Could not decode image: {exc}") from exc

    if rgb.size == 0:
        raise UnsupportedImageError("Decoded image has zero size.")

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    return bgr


def encode_png_data_uri(image: np.ndarray) -> str:
    """Encode a (grayscale or BGR) numpy image as a base64 PNG data URI."""
    if image.ndim == 2:
        encode_target = image
    else:
        encode_target = image

    success, buffer = cv2.imencode(".png", encode_target)
    if not success:
        raise RuntimeError("Failed to encode preview image as PNG.")

    b64 = base64.b64encode(buffer.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def bgr_to_size(image: np.ndarray) -> Tuple[int, int]:
    """Return (width, height) for a numpy image array."""
    h, w = image.shape[:2]
    return w, h
