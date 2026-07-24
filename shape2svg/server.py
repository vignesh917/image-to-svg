#!/usr/bin/env python3
"""shape2svg web app.

Run:  uvicorn server:app --reload --port 8000   (or: python server.py)
Then open http://localhost:8000
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from shape2svg import PipelineConfig, process_image
from shape2svg.pipeline import render_overlay
from shape2svg.preprocess import decode_image

app = FastAPI(title="shape2svg", version="1.0.0")
STATIC = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/extract")
async def extract(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
    epsilon: float = Form(0.005),
    min_area: float = Form(0.005),
    max_regions: int = Form(8),
    hull: bool = Form(False),
    holes: bool = Form(True),
    merge: Optional[int] = Form(None),
    min_length: Optional[float] = Form(None),
    blur: Optional[int] = Form(None),
    join: bool = Form(True),
    join_angle: float = Form(40.0),
    invert: str = Form("auto"),
    stroke_width: float = Form(2.0),
    max_dim: int = Form(1200),
    overlay: bool = Form(True),
):
    data = await file.read()
    try:
        img = decode_image(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

    cfg = PipelineConfig(
        mode=mode, max_dim=max_dim, blur_kernel=blur,
        invert=None if invert == "auto" else (invert == "yes"),
        min_area_ratio=min_area, max_regions=max_regions, epsilon_frac=epsilon,
        use_hull=hull, include_holes=holes,
        merge_kernel=merge, min_length_frac=min_length,
        join_segments=join, join_angle_deg=join_angle,
        stroke_width=stroke_width,
    )
    try:
        result = process_image(img, cfg)
    except Exception as e:  # surface pipeline errors to the UI
        raise HTTPException(422, f"extraction failed: {e}")

    payload = {"svg": result.svg, "stats": result.stats, "json": result.json,
               "width": result.width, "height": result.height}
    if overlay:
        ov = render_overlay(img, result, thickness=max(2, result.width // 500))
        ok, buf = cv2.imencode(".jpg", ov, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if ok:
            payload["overlay"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()
    return JSONResponse(payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
