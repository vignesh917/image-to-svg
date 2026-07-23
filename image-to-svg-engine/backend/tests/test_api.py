"""End-to-end API tests using FastAPI's TestClient (no network needed)."""
from __future__ import annotations

import io
import json

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _rectangle_png_bytes() -> bytes:
    canvas = np.full((400, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(canvas, (80, 80), (320, 320), (0, 0, 0), thickness=4)
    ok, buf = cv2.imencode(".png", canvas)
    assert ok
    return buf.tobytes()


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_formats():
    resp = client.get("/api/formats")
    assert resp.status_code == 200
    body = resp.json()
    assert ".png" in body["extensions"]
    assert ".tiff" in body["extensions"] or ".tif" in body["extensions"]


def test_process_default_params():
    files = {"file": ("rect.png", _rectangle_png_bytes(), "image/png")}
    resp = client.post("/api/process", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["objects"]) == 1
    assert body["svg"].startswith("<svg")
    assert body["image_size"]["width"] == 400
    assert body["image_size"]["height"] == 400


def test_process_with_custom_params():
    params = {"epsilon_factor": 0.02, "shape_type": "polygon", "stroke_color": "#ff0000"}
    files = {"file": ("rect.png", _rectangle_png_bytes(), "image/png")}
    resp = client.post("/api/process", files=files, data={"params": json.dumps(params)})
    assert resp.status_code == 200
    body = resp.json()
    assert "<polygon" in body["svg"]
    assert body["params_used"]["stroke_color"] == "#ff0000"


def test_process_rejects_empty_file():
    files = {"file": ("empty.png", b"", "image/png")}
    resp = client.post("/api/process", files=files)
    assert resp.status_code == 400


def test_process_rejects_garbage_bytes():
    files = {"file": ("not-an-image.png", b"this is not a real image", "image/png")}
    resp = client.post("/api/process", files=files)
    assert resp.status_code == 400


def test_sauvola_without_skimage_gives_clean_400_or_succeeds():
    """
    If scikit-image is installed, 'sauvola' mode should just work. If it
    is NOT installed (a valid, supported configuration - it's an optional
    extra), the API must fail cleanly with a 400 and a helpful message
    instead of a raw 500/traceback. Either outcome is acceptable here;
    what's under test is that there is no unhandled-exception 500.
    """
    params = {"threshold_mode": "sauvola"}
    files = {"file": ("rect.png", _rectangle_png_bytes(), "image/png")}
    resp = client.post("/api/process", files=files, data={"params": json.dumps(params)})
    assert resp.status_code in (200, 400)
    if resp.status_code == 400:
        assert "scikit-image" in resp.json()["detail"]


def test_process_blank_image_returns_422():
    blank = np.full((300, 300, 3), 255, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", blank)
    assert ok
    files = {"file": ("blank.png", buf.tobytes(), "image/png")}
    resp = client.post("/api/process", files=files, data={"params": json.dumps({"min_area_ratio": 0.01})})
    assert resp.status_code == 422
