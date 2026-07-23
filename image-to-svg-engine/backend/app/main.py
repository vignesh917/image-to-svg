"""
FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload --port 8000
Docs at:   http://localhost:8000/docs  (Swagger)  or  /redoc
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.routes import router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Generic image -> SVG outline extraction engine. Upload any image "
        "containing a bounded shape (site boundary, railway layout, floor "
        "plan, building outline, road layout, polygon, ...) and receive a "
        "clean, simplified SVG of its outline. No per-image configuration "
        "or code changes required."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Belt-and-braces catch-all so a truly unexpected error still returns
    a clean JSON error body instead of a bare 500 with an HTML traceback."""
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "internal_error", "detail": str(exc)},
    )
