"""
REST API routes.

Only one endpoint does the real work (`POST /api/process`); it accepts any
supported image plus an optional JSON-encoded parameter set and returns
every pipeline stage, the detected geometry, and the final SVG in one
response. Everything else (health, format discovery) is bookkeeping for
the frontend and API consumers.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.api.converters import object_result_to_schema, params_to_config
from app.config import settings
from app.models.schemas import (
    ImageSize,
    ProcessingParams,
    ProcessingResult,
    StagePreviews,
    SupportedFormats,
)
from app.opencv_pipeline.pipeline import PipelineError, process_image
from app.utils.image_io import UnsupportedImageError, decode_image, encode_png_data_uri

logger = logging.getLogger("app.api")

router = APIRouter(prefix=settings.API_PREFIX, tags=["image-to-svg"])


@router.get("/health")
def health() -> dict:
    """Liveness/readiness probe."""
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/formats", response_model=SupportedFormats)
def supported_formats() -> SupportedFormats:
    """Let the frontend (or any API consumer) discover accepted formats and
    limits at runtime instead of hardcoding them client-side."""
    return SupportedFormats(
        extensions=settings.SUPPORTED_EXTENSIONS,
        content_types=settings.SUPPORTED_CONTENT_TYPES,
        max_upload_mb=settings.MAX_UPLOAD_MB,
    )


@router.post("/process", response_model=ProcessingResult)
async def process(file: UploadFile, params: str | None = Form(default=None)) -> ProcessingResult:
    """
    Run the full image -> SVG pipeline on an uploaded image.

    - **file**: any of PNG / JPEG / WEBP / BMP / TIFF.
    - **params**: optional JSON string matching `ProcessingParams`; any
      field left out falls back to its documented default, so a bare
      upload with no params at all still works end-to-end.
    """
    raw_bytes = await file.read()

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.MAX_UPLOAD_MB}MB upload limit.",
        )
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        parsed_params = ProcessingParams.model_validate_json(params) if params else ProcessingParams()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid params: {exc}") from exc

    try:
        image_bgr = decode_image(raw_bytes)
    except UnsupportedImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = params_to_config(parsed_params)

    try:
        result = process_image(image_bgr, config)
    except PipelineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # e.g. an optional dependency (scikit-image) was requested but isn't installed.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled pipeline failure")
        raise HTTPException(
            status_code=500, detail="Internal error while processing the image."
        ) from None

    stages = StagePreviews(
        original=encode_png_data_uri(result.stage_images["original"]),
        grayscale=encode_png_data_uri(result.stage_images["grayscale"]),
        blurred=encode_png_data_uri(result.stage_images["blurred"]),
        threshold=encode_png_data_uri(result.stage_images["threshold"]),
        edges=encode_png_data_uri(result.stage_images["edges"]),
        contours_overlay=encode_png_data_uri(result.stage_images["contours_overlay"]),
    )

    return ProcessingResult(
        success=True,
        image_size=ImageSize(width=result.width, height=result.height),
        stages=stages,
        objects=[object_result_to_schema(o) for o in result.objects],
        svg=result.svg,
        view_box=f"0 0 {result.view_box.width:.2f} {result.view_box.height:.2f}",
        params_used=parsed_params,
    )
