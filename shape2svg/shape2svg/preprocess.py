"""Image loading, resizing and binarization.

Everything here is data-driven: thresholds are derived from the image's own
statistics (Otsu / median), never hardcoded for a particular picture.
"""
from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    """Load an image as BGR. Raises ValueError on failure."""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def decode_image(data: bytes) -> np.ndarray:
    """Decode raw bytes (upload) as BGR."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    return img


def resize_max_dim(img: np.ndarray, max_dim: int) -> Tuple[np.ndarray, float]:
    """Downscale so max(h, w) <= max_dim.

    Returns (resized, scale) where original_coords = resized_coords / scale.
    Coordinates are always mapped back to the ORIGINAL pixel grid, so the
    output SVG keeps the exact proportions of the input image.
    """
    h, w = img.shape[:2]
    m = max(h, w)
    if max_dim <= 0 or m <= max_dim:
        return img, 1.0
    scale = max_dim / m
    resized = cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)
    return resized, scale


def to_gray(img: np.ndarray, use_clahe: bool = False) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    return gray


def denoise(gray: np.ndarray, blur_kernel: int = 5, bilateral: bool = False) -> np.ndarray:
    """Blur to suppress texture (grass, gravel, sleepers) before detection."""
    if bilateral:
        gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)
    k = max(1, blur_kernel) | 1  # force odd
    if k > 1:
        gray = cv2.GaussianBlur(gray, (k, k), 0)
    return gray


def binarize(
    gray: np.ndarray,
    mode: str = "otsu",
    invert: Optional[bool] = None,
    adaptive_block: int = 35,
    adaptive_c: int = 5,
) -> np.ndarray:
    """Binarize with automatic polarity.

    invert=None -> auto polarity: the class that owns the image border is
    treated as background (a shape rarely owns the frame, even when it covers
    more than half the pixels). Falls back to the minority rule when border
    ownership is ambiguous.
    """
    if mode == "adaptive":
        block = max(3, adaptive_block) | 1
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, adaptive_c
        )
    else:  # otsu
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if invert is None:
        white = binary > 0
        border = np.concatenate([white[0, :], white[-1, :], white[:, 0], white[:, -1]])
        border_white = float(border.mean())
        if abs(border_white - 0.5) > 0.2:
            invert = border_white > 0.5   # border owner is background
        else:
            invert = float(white.mean()) > 0.5  # ambiguous border: minority rule
    if invert:
        binary = cv2.bitwise_not(binary)
    return binary


def auto_canny(gray: np.ndarray, sigma: float = 0.33) -> np.ndarray:
    """Canny with thresholds derived from the image median (classic auto-canny)."""
    v = float(np.median(gray))
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    if upper <= lower:
        upper = lower + 1
    return cv2.Canny(gray, lower, upper)


def morph_close(binary: np.ndarray, kernel: int = 5, iterations: int = 1) -> np.ndarray:
    if kernel <= 1 or iterations <= 0:
        return binary
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k, iterations=iterations)


def morph_open(binary: np.ndarray, kernel: int = 3, iterations: int = 1) -> np.ndarray:
    if kernel <= 1 or iterations <= 0:
        return binary
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, k, iterations=iterations)


def dilate(binary: np.ndarray, kernel: int = 3, iterations: int = 1) -> np.ndarray:
    if kernel <= 1 or iterations <= 0:
        return binary
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    return cv2.dilate(binary, k, iterations=iterations)
