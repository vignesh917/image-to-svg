"""Stage 4 of the pipeline: Canny edge detection."""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def auto_canny_thresholds(image: np.ndarray, sigma: float = 0.33) -> Tuple[int, int]:
    """
    Derive Canny thresholds from the image's own median intensity instead of
    a fixed constant. This is the key to "no code changes for a new image":
    a dim scan and a bright drone photo both get thresholds appropriate to
    their own contrast, automatically.
    """
    median = float(np.median(image))
    lower = int(max(0, (1.0 - sigma) * median))
    upper = int(min(255, (1.0 + sigma) * median))
    if upper <= lower:
        upper = lower + 1
    return lower, upper


def canny_edges(binary_or_gray: np.ndarray, low: int, high: int) -> np.ndarray:
    """Run Canny edge detection with explicit thresholds."""
    return cv2.Canny(binary_or_gray, low, high, L2gradient=True)
