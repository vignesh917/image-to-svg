"""Automatic mode selection: 'regions' vs 'lines'.

Heuristic (computed on a small copy of the image, from its own statistics):

  thinness = skeleton_pixels / foreground_pixels  after auto-binarization.

Solid blobs (a filled site outline, a lake, a logo) have thinness near 0 -
the skeleton collapses to a few medial-axis pixels. Stroke-like content
(tracks, roads, walls, wire-frame drawings, textured aerial photos) keeps
thinness high because the foreground is already 1-few pixels wide.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from skimage.morphology import skeletonize

from shape2svg import preprocess as prep

THINNESS_THRESHOLD = 0.22
EDGE_DENSITY_THRESHOLD = 0.08
ANALYSIS_DIM = 512


@dataclass
class ModeDecision:
    mode: str            # "regions" | "lines"
    thinness: float
    foreground_frac: float
    near_binary: bool    # input already looks like a drawing / scan
    edge_density: float  # Canny pixels / total pixels (texture measure)
    reason: str = ""


def analyze(img_bgr: np.ndarray) -> ModeDecision:
    small, _ = prep.resize_max_dim(img_bgr, ANALYSIS_DIM)
    gray = prep.to_gray(small)
    gray_b = prep.denoise(gray, blur_kernel=3)

    # Is the input near-binary (drawing/scan) rather than a photo?
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist /= max(1.0, hist.sum())
    extremes = hist[:32].sum() + hist[224:].sum()
    near_binary = bool(extremes > 0.85)

    binary = prep.binarize(gray_b, mode="otsu")
    fg = binary > 0
    fg_frac = float(fg.mean())
    edge_density = float((prep.auto_canny(gray_b) > 0).mean())

    if fg_frac == 0.0:
        return ModeDecision("lines", 1.0, 0.0, near_binary, edge_density, "empty foreground")

    skel = skeletonize(fg)
    thinness = float(skel.sum()) / float(fg.sum())

    if near_binary:
        # drawing/scan: thin strokes -> trace lines; solid marks -> outlines
        mode = "lines" if thinness > THINNESS_THRESHOLD else "regions"
        reason = f"near-binary drawing, thinness={thinness:.3f}"
    elif edge_density > EDGE_DENSITY_THRESHOLD:
        # texture-rich photo (aerial scenes, tracks, roads): trace the line network
        mode = "lines"
        reason = f"textured photo, edge_density={edge_density:.3f}"
    else:
        # clean photo of a distinct object/area: extract its boundary
        mode = "lines" if thinness > THINNESS_THRESHOLD else "regions"
        reason = f"clean photo, thinness={thinness:.3f}"
    return ModeDecision(mode, thinness, fg_frac, near_binary, edge_density, reason)
