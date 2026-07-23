"""
Stage 1-3 of the pipeline: grayscale, denoise/blur, threshold -> binary mask.

Each function takes a numpy array and plain scalars, and returns a numpy
array. This keeps every step independently unit-testable and means the
same code path runs identically whether the input is a railway yard photo,
a floor plan scan, or a CAD export.
"""
from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(image_bgr: np.ndarray) -> np.ndarray:
    """Convert a BGR image to single-channel grayscale."""
    if image_bgr.ndim == 2:
        return image_bgr
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def _odd(value: int) -> int:
    """OpenCV kernel sizes must be odd and >= 1."""
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1


def denoise(gray: np.ndarray) -> np.ndarray:
    """Light non-local-means denoising to reduce photographic sensor noise
    before blurring. Cheap enough for typical upload sizes and makes the
    adaptive threshold noticeably more stable on real photos (as opposed
    to clean line-art)."""
    return cv2.fastNlMeansDenoising(gray, h=7, templateWindowSize=7, searchWindowSize=21)


def gaussian_blur(gray: np.ndarray, kernel_size: int) -> np.ndarray:
    """Gaussian blur to suppress high-frequency texture/noise that would
    otherwise fragment the Canny edge map into thousands of tiny edges."""
    k = _odd(kernel_size)
    if k <= 1:
        return gray
    return cv2.GaussianBlur(gray, (k, k), 0)


def remove_background(gray: np.ndarray) -> np.ndarray:
    """
    Suppress a roughly uniform background via flood fill from the four
    border midpoints. This is a lightweight, model-free background removal
    step (bonus feature): it does not assume any particular subject, only
    that the corners/edges of the frame are background, which holds for
    aerial/top-down shots of a bounded site, plan scans on a table, etc.

    Returns a mask (255 = likely foreground) that callers can combine with
    later stages; it is intentionally conservative and used only as a soft
    prior, not a hard cutout.
    """
    h, w = gray.shape[:2]
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    work = blurred.copy()

    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
             (w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1)]
    diff = (12, 12)
    for seed in seeds:
        flood_mask[:] = 0
        try:
            cv2.floodFill(work, flood_mask, seed, 255, diff, diff,
                           flags=cv2.FLOODFILL_FIXED_RANGE | 8)
        except cv2.error:
            continue

    background = flood_mask[1:-1, 1:-1]
    foreground = cv2.bitwise_not(cv2.multiply(background, 255))
    return foreground


def adaptive_threshold(gray: np.ndarray, block_size: int, c: int, invert: bool) -> np.ndarray:
    """Adaptive (locally-varying) threshold - robust to uneven illumination,
    which is the common case for photographs (as opposed to a flat scan)."""
    block = _odd(block_size)
    block = max(block, 3)
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, mode, block, c
    )


def sauvola_threshold(gray: np.ndarray, window_size: int, k: float, invert: bool) -> np.ndarray:
    """
    Sauvola local thresholding (scikit-image) - generally outperforms plain
    adaptive mean thresholding on photographs with strong local contrast
    variation (e.g. aerial/drone shots with mixed sun and shadow across a
    site). This is an optional codepath: scikit-image is only imported
    here, on demand, so the rest of the application works with just
    OpenCV/NumPy/Pillow if scikit-image isn't installed.
    """
    try:
        from skimage.filters import threshold_sauvola
    except ImportError as exc:  # pragma: no cover - exercised only when the
        # optional dependency is missing.
        raise RuntimeError(
            "threshold_mode='sauvola' requires scikit-image. Install it with "
            "`pip install scikit-image` or choose 'adaptive'/'otsu' instead."
        ) from exc

    window = _odd(window_size)
    window = max(window, 3)
    local_thresh = threshold_sauvola(gray, window_size=window, k=k)
    mask = gray > local_thresh
    if invert:
        mask = ~mask
    return (mask.astype(np.uint8)) * 255


def otsu_threshold(gray: np.ndarray, invert: bool) -> np.ndarray:
    """Global Otsu threshold - fast, reliable fallback for evenly-lit images
    (clean scans, rendered plans, screenshots)."""
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, 0, 255, mode | cv2.THRESH_OTSU)
    return binary


def binary_threshold(gray: np.ndarray, invert: bool, value: int = 127) -> np.ndarray:
    """Fixed-value binary threshold - useful for already-binarized or very
    high-contrast inputs (e.g. pre-made masks)."""
    mode = cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
    _, binary = cv2.threshold(gray, value, 255, mode)
    return binary


def morphological_closing(binary: np.ndarray, kernel_size: int) -> np.ndarray:
    """Close small gaps in the mask/edge map (dilate then erode) so a
    boundary broken up by noise or texture reconnects into one contour."""
    if kernel_size <= 0:
        return binary
    k = _odd(kernel_size)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def morphological_open(binary: np.ndarray, kernel_size: int) -> np.ndarray:
    """Remove small speckle noise (erode then dilate) prior to contour search."""
    if kernel_size <= 0:
        return binary
    k = _odd(kernel_size)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
