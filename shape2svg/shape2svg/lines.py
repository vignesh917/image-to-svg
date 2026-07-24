"""Line mode: extract a network of curves (tracks, roads, walls, strokes).

Photo path:    blur -> auto-Canny -> dilate (merges rail+sleeper texture into
               one band per track) -> skeletonize -> centerlines.
Drawing path:  threshold (thin dark strokes) -> skeletonize -> centerlines.

The skeleton is traced into polylines with a graph walk (endpoints/junctions
as nodes), then Douglas-Peucker simplified and length-filtered.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import cv2
import numpy as np
from skimage.morphology import skeletonize

Pixel = Tuple[int, int]  # (y, x)


@dataclass
class Polyline:
    points: np.ndarray  # (N, 2) float, (x, y)
    length: float = 0.0
    closed: bool = False

    def scaled(self, factor: float) -> "Polyline":
        return Polyline(points=self.points * factor, length=self.length * factor, closed=self.closed)


def _polyline_length(pts: np.ndarray) -> float:
    if len(pts) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


def _neighbors(p: Pixel, coords: Set[Pixel]) -> List[Pixel]:
    y, x = p
    out = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            q = (y + dy, x + dx)
            if q in coords:
                out.append(q)
    return out


def trace_skeleton(skel: np.ndarray) -> List[List[Pixel]]:
    """Convert a 1-px-wide skeleton into pixel paths.

    Nodes are endpoints (degree 1) and junctions (degree >= 3); paths are the
    degree-2 chains between them. Pure cycles are traced separately.
    """
    ys, xs = np.nonzero(skel)
    coords: Set[Pixel] = set(zip(ys.tolist(), xs.tolist()))
    if not coords:
        return []

    degree: Dict[Pixel, int] = {}
    nbrs: Dict[Pixel, List[Pixel]] = {}
    for p in coords:
        n = _neighbors(p, coords)
        nbrs[p] = n
        degree[p] = len(n)

    nodes = {p for p in coords if degree[p] != 2}
    visited: Set[Tuple[Pixel, Pixel]] = set()

    def edge(a: Pixel, b: Pixel) -> Tuple[Pixel, Pixel]:
        return (a, b) if a <= b else (b, a)

    paths: List[List[Pixel]] = []
    for start in nodes:
        for first in nbrs[start]:
            if edge(start, first) in visited:
                continue
            path = [start, first]
            visited.add(edge(start, first))
            prev, cur = start, first
            while cur not in nodes:
                nxt = None
                for q in nbrs[cur]:
                    if q != prev and edge(cur, q) not in visited:
                        nxt = q
                        break
                if nxt is None:
                    break
                visited.add(edge(cur, nxt))
                path.append(nxt)
                prev, cur = cur, nxt
            paths.append(path)

    # pure cycles: every pixel degree 2, none adjacent to a node
    in_path: Set[Pixel] = set()
    for path in paths:
        in_path.update(path)
    leftovers = coords - in_path
    while leftovers:
        start = leftovers.pop()
        path = [start]
        prev: Pixel | None = None
        cur = start
        while True:
            nxt = None
            for q in nbrs[cur]:
                if q != prev and edge(cur, q) not in visited:
                    nxt = q
                    break
            if nxt is None:
                break
            visited.add(edge(cur, nxt))
            path.append(nxt)
            prev, cur = cur, nxt
            leftovers.discard(cur)
            if cur == start:
                break
        if len(path) > 2:
            paths.append(path)
    return paths


def _simplify_open(pts_xy: np.ndarray, epsilon: float, closed: bool) -> np.ndarray:
    curve = pts_xy.reshape(-1, 1, 2).astype(np.float32)
    approx = cv2.approxPolyDP(curve, epsilon, closed)
    return approx.reshape(-1, 2).astype(float)


# ------------------------------------------------------- junction joining

def _end_direction(path: List[Pixel], end: int, k: int = 7) -> np.ndarray:
    """Unit vector pointing OUT of the path at the given end (0=start, 1=end)."""
    pts = np.array(path, dtype=float)  # (y, x)
    if end == 0:
        a, b = pts[min(k, len(pts) - 1)], pts[0]
    else:
        a, b = pts[max(0, len(pts) - 1 - k)], pts[-1]
    v = b - a
    n = np.linalg.norm(v)
    return v / n if n > 0 else np.array([0.0, 0.0])


def join_segments(
    pixel_paths: List[List[Pixel]],
    max_gap: int = 3,
    max_angle_deg: float = 40.0,
    min_seed_len: int = 5,
) -> List[List[Pixel]]:
    """Merge skeleton segments that continue smoothly through junctions.

    Track crossings, wall T-junctions etc. split the skeleton into short
    chains; here each junction pairs up the two incident segments whose
    directions best continue each other (within max_angle_deg), and chains
    are concatenated. This is what turns confetti into long clean curves.
    """
    paths = [p for p in pixel_paths if len(p) >= 2]
    if not paths:
        return []

    # endpoint records: (path_idx, end) -> pixel, direction
    ends = []
    for i, p in enumerate(paths):
        if len(p) >= min_seed_len:
            ends.append((i, 0, p[0], _end_direction(p, 0)))
            ends.append((i, 1, p[-1], _end_direction(p, 1)))

    # cluster endpoints by proximity (Chebyshev <= max_gap) via grid hashing
    grid: Dict[Pixel, List[int]] = {}
    for idx, (_, _, px, _) in enumerate(ends):
        grid.setdefault((px[0] // (max_gap + 1), px[1] // (max_gap + 1)), []).append(idx)

    def near(idx: int) -> List[int]:
        _, _, (y, x), _ = ends[idx]
        cy, cx = y // (max_gap + 1), x // (max_gap + 1)
        out = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for j in grid.get((cy + dy, cx + dx), []):
                    if j != idx:
                        py, pxx = ends[j][2]
                        if abs(py - y) <= max_gap and abs(pxx - x) <= max_gap:
                            out.append(j)
        return out

    # greedy pairing by best angular continuation
    cos_max = np.cos(np.deg2rad(max_angle_deg))
    candidates = []
    for a in range(len(ends)):
        for b in near(a):
            if b <= a or ends[a][0] == ends[b][0]:
                continue
            # a's outgoing direction should oppose b's outgoing direction
            c = float(-np.dot(ends[a][3], ends[b][3]))
            if c >= cos_max:
                candidates.append((c, a, b))
    candidates.sort(reverse=True)
    partner: Dict[int, int] = {}
    for c, a, b in candidates:
        if a not in partner and b not in partner:
            partner[a] = b
            partner[b] = a

    # walk chains of paths connected through paired ends
    end_id = {(ends[i][0], ends[i][1]): i for i in range(len(ends))}
    used = [False] * len(paths)
    merged: List[List[Pixel]] = []

    def orient(i: int, start_end: int) -> List[Pixel]:
        return paths[i] if start_end == 0 else paths[i][::-1]

    for i, p in enumerate(paths):
        if used[i]:
            continue
        if len(p) < min_seed_len:
            used[i] = True
            merged.append(p)
            continue
        # find a free (unpaired) end to start from; fall back to end 0 (cycle)
        start_end = 0
        for e in (0, 1):
            eid = end_id.get((i, e))
            if eid is None or eid not in partner:
                start_end = e
                break
        chain = orient(i, start_end)
        used[i] = True
        cur, cur_exit = i, 1 - start_end
        while True:
            eid = end_id.get((cur, cur_exit))
            if eid is None or eid not in partner:
                break
            nxt_eid = partner[eid]
            nxt, nxt_entry = ends[nxt_eid][0], ends[nxt_eid][1]
            if used[nxt]:
                break  # cycle closed
            chain = chain + orient(nxt, nxt_entry)
            used[nxt] = True
            cur, cur_exit = nxt, 1 - nxt_entry
        merged.append(chain)
    return merged


def extract_lines(
    gray_blurred: np.ndarray,
    source_binary: np.ndarray | None = None,
    merge_kernel: int = 5,
    min_length_frac: float = 0.02,
    epsilon_px: float = 2.0,
    max_paths: int = 400,
    join: bool = True,
    join_angle_deg: float = 40.0,
) -> List[Polyline]:
    """Extract the line network.

    source_binary: if given (near-binary drawings), skeletonize it directly.
    Otherwise run auto-Canny on the blurred grayscale and merge edge texture
    with a dilation of `merge_kernel` before skeletonizing.
    """
    h, w = gray_blurred.shape[:2]
    diag = float(np.hypot(h, w))
    min_len = min_length_frac * diag

    if source_binary is not None:
        band = source_binary
    else:
        edges = cv2.Canny(gray_blurred, *_auto_canny_thresholds(gray_blurred))
        k = max(1, merge_kernel)
        kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        band = cv2.dilate(edges, kern, iterations=1)
        band = cv2.morphologyEx(band, cv2.MORPH_CLOSE, kern, iterations=1)

    skel = skeletonize(band > 0)
    pixel_paths = trace_skeleton(skel)
    if join:
        pixel_paths = join_segments(pixel_paths, max_angle_deg=join_angle_deg)

    polylines: List[Polyline] = []
    for path in pixel_paths:
        if len(path) < 2:
            continue
        pts = np.array([(x, y) for (y, x) in path], dtype=float)
        closed = bool(len(path) > 3 and path[0] == path[-1])
        pts = _simplify_open(pts, epsilon_px, closed)
        if len(pts) < 2:
            continue
        length = _polyline_length(pts)
        if closed:
            length += float(np.linalg.norm(pts[0] - pts[-1]))
        if length < min_len:
            continue
        polylines.append(Polyline(points=pts, length=length, closed=closed))

    polylines.sort(key=lambda p: p.length, reverse=True)
    return polylines[:max_paths]


def _auto_canny_thresholds(gray: np.ndarray, sigma: float = 0.33) -> Tuple[int, int]:
    v = float(np.median(gray))
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    if upper <= lower:
        upper = lower + 1
    return lower, upper
