"""Generalisation tests on synthetic images the pipeline has never seen.

Run:  python -m pytest tests/ -q
"""
import cv2
import numpy as np
import pytest

from shape2svg import PipelineConfig, process_image
from shape2svg.autodetect import analyze


def _iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    inter = np.logical_and(mask_a, mask_b).sum()
    union = np.logical_or(mask_a, mask_b).sum()
    return inter / union if union else 0.0


def _star_image(size=600, points=7):
    img = np.full((size, size, 3), 245, np.uint8)
    cx, cy, r1, r2 = size // 2, size // 2, size * 0.42, size * 0.18
    pts = []
    for i in range(points * 2):
        r = r1 if i % 2 == 0 else r2
        a = np.pi * i / points - np.pi / 2
        pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    poly = np.array(pts, np.int32)
    cv2.fillPoly(img, [poly], (40, 40, 40))
    return img, poly


def _donut_image(size=500):
    img = np.full((size, size, 3), 250, np.uint8)
    cv2.circle(img, (size // 2, size // 2), int(size * 0.4), (30, 30, 30), -1)
    cv2.circle(img, (size // 2, size // 2), int(size * 0.18), (250, 250, 250), -1)
    return img


def _floorplan_image(w=800, h=600):
    """Thin dark wall strokes on white - a drawing, not a photo."""
    img = np.full((h, w, 3), 255, np.uint8)
    walls = [((60, 60), (740, 60)), ((740, 60), (740, 540)), ((740, 540), (60, 540)),
             ((60, 540), (60, 60)), ((400, 60), (400, 300)), ((60, 300), (400, 300))]
    for a, b in walls:
        cv2.line(img, a, b, (20, 20, 20), 3)
    return img


def _rasterize(regions, shape):
    mask = np.zeros(shape[:2], np.uint8)
    for r in regions:
        cv2.fillPoly(mask, [r.points.astype(np.int32)], 1)
        for hole in r.holes:
            cv2.fillPoly(mask, [hole.astype(np.int32)], 0)
    return mask.astype(bool)


def test_star_regions_high_iou():
    img, poly = _star_image()
    result = process_image(img, PipelineConfig(mode="auto"))
    assert result.mode == "regions", "solid shape should auto-select regions"
    truth = np.zeros(img.shape[:2], np.uint8)
    cv2.fillPoly(truth, [poly], 1)
    iou = _iou(_rasterize(result.regions, img.shape), truth.astype(bool))
    assert iou > 0.97, f"star IoU too low: {iou:.3f}"
    assert "<svg" in result.svg and "viewBox" in result.svg


def test_donut_hole_preserved():
    img = _donut_image()
    result = process_image(img, PipelineConfig(mode="regions"))
    assert len(result.regions) >= 1
    assert len(result.regions[0].holes) >= 1, "interior hole must be preserved"
    # ring area = outer - inner
    truth = np.zeros(img.shape[:2], np.uint8)
    cv2.circle(truth, (250, 250), 200, 1, -1)
    cv2.circle(truth, (250, 250), 90, 0, -1)
    iou = _iou(_rasterize(result.regions, img.shape), truth.astype(bool))
    assert iou > 0.95, f"donut IoU too low: {iou:.3f}"


def test_floorplan_lines_mode():
    img = _floorplan_image()
    decision = analyze(img)
    assert decision.near_binary
    result = process_image(img, PipelineConfig(mode="auto"))
    assert result.mode == "lines", "thin-stroke drawing should auto-select lines"
    total = sum(p.length for p in result.polylines)
    # total wall length ~ 3*680 + 2*480 + 240 + 340 = 3620 px
    assert total > 2500, f"line network too short: {total:.0f}px"


def test_proportions_preserved():
    """Output viewBox always matches the source image exactly."""
    img, _ = _star_image(size=600)
    wide = cv2.resize(img, (1200, 600))
    result = process_image(wide)
    assert 'viewBox="0 0 1200 600"' in result.svg


def test_coordinates_within_bounds():
    img, _ = _star_image()
    result = process_image(img)
    for r in result.regions:
        assert r.points[:, 0].max() <= img.shape[1] and r.points[:, 1].max() <= img.shape[0]
        assert r.points.min() >= 0


def test_json_export_roundtrip():
    import json
    img, _ = _star_image()
    result = process_image(img)
    doc = json.loads(result.json)
    assert doc["image"]["width"] == 600
    assert len(doc["regions"]) == len(result.regions)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
