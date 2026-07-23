# Image → SVG Extraction Engine

A production-ready, general-purpose engine that converts **any** image containing a bounded shape - a site boundary, railway/track layout, floor plan, building outline, road layout, or arbitrary polygon - into a clean, simplified SVG outline.

There is no per-image logic anywhere in this codebase. The entire behaviour is a function of pixels in, parameters in, geometry out. Upload a different photo tomorrow and the same code path runs; nothing needs to change.

```
Image Upload
  -> Grayscale
  -> Denoise + Gaussian Blur
  -> Threshold (adaptive / Sauvola / Otsu / binary) -> Binary Image
  -> Canny Edge Detection (auto-thresholded from the image's own histogram)
  -> Morphological Closing (bridges small gaps)
  -> Contour Detection (cv2.findContours, RETR_EXTERNAL)
  -> Largest / N-largest Contour Selection (area-filtered)
  -> [optional] Convex Hull / Chaikin Smoothing
  -> Douglas-Peucker Polygon Simplification (cv2.approxPolyDP)
  -> Coordinate Normalization (translate-only - preserves scale/angles/aspect ratio)
  -> SVG Path / Polygon Generation (auto-fitted viewBox)
  -> Live preview + Download (SVG / JSON / PNG)
```

## Table of contents

1. [Quickstart](#quickstart)
2. [Architecture](#architecture)
3. [Project structure](#project-structure)
4. [Installation](#installation)
5. [Running with Docker](#running-with-docker)
6. [Using the app](#using-the-app)
7. [API reference](#api-reference)
8. [How the pipeline works](#how-the-pipeline-works)
9. [Why coordinates are never hardcoded](#why-coordinates-are-never-hardcoded)
10. [Testing](#testing)
11. [Examples](#examples)
12. [Limitations & extending the engine](#limitations--extending-the-engine)

## Quickstart

```bash
# Terminal 1 - backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**, drag in an image, and the SVG outline appears automatically. Full interactive API docs (Swagger UI) are served by the backend itself at **http://localhost:8000/docs**.

## Architecture

```
┌─────────────────────┐        REST (multipart/form-data)        ┌──────────────────────┐
│   React 19 + TS      │  ───────────────────────────────────▶   │       FastAPI         │
│   Vite + Tailwind    │  ◀───────────────────────────────────   │                        │
│                      │        JSON (stages, geometry, SVG)     │  ┌──────────────────┐  │
│  UploadDropzone      │                                          │  │ opencv_pipeline/  │  │
│  ParameterControls   │                                          │  │  preprocessing.py │  │
│  StagePreviewTabs    │                                          │  │  edges.py         │  │
│  SvgViewer (pan/zoom)│                                          │  │  contours.py      │  │
│  PointsTable         │                                          │  │  normalize.py     │  │
│  DownloadBar         │                                          │  │  pipeline.py      │  │
└─────────────────────┘                                          │  └──────────────────┘  │
                                                                   │  ┌──────────────────┐  │
                                                                   │  │ svg/generator.py  │  │
                                                                   │  └──────────────────┘  │
                                                                   │  ┌──────────────────┐  │
                                                                   │  │ api/routes.py     │  │
                                                                   │  └──────────────────┘  │
                                                                   └──────────────────────┘
```

The CV engine (`backend/app/opencv_pipeline/` + `backend/app/svg/`) has **zero dependency on FastAPI or pydantic** - it's plain Python dataclasses, NumPy arrays, and OpenCV calls. `backend/app/api/converters.py` is the only file that bridges it to the web layer. That means the engine can be dropped into a CLI tool, a batch job, or a different web framework without modification.

## Project structure

```
image-to-svg-engine/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, global error handler
│   │   ├── config.py                # Central, env-overridable settings
│   │   ├── api/
│   │   │   ├── routes.py            # /api/health, /api/formats, /api/process
│   │   │   └── converters.py        # pydantic <-> pipeline dataclass glue
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic request/response contracts
│   │   ├── opencv_pipeline/         # the "opencv/" stage from the spec
│   │   │   ├── preprocessing.py     # grayscale, denoise, blur, threshold, morphology
│   │   │   ├── edges.py             # Canny + auto-threshold derivation
│   │   │   ├── contours.py          # findContours, selection, hull, smoothing, DP simplify
│   │   │   ├── normalize.py         # bounding box + translate/scale-preserving normalization
│   │   │   └── pipeline.py          # orchestrates every stage end-to-end
│   │   ├── svg/                     # the "svg/" stage from the spec
│   │   │   └── generator.py         # native SVG <path>/<polygon> + viewBox generation
│   │   └── utils/
│   │       └── image_io.py          # format-agnostic decode (PNG/JPEG/WEBP/BMP/TIFF)
│   ├── tests/                       # pytest suite (pipeline + API)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/              # UploadDropzone, ParameterControls, SvgViewer, ...
│   │   ├── hooks/useImageProcessor.ts
│   │   ├── api/client.ts
│   │   └── types/index.ts
│   ├── package.json
│   └── Dockerfile
├── examples/
│   ├── input/                       # sample images covering every listed shape category
│   └── output/                      # the .svg + .json this engine produced for each
├── docs/
│   ├── API.md                       # full endpoint reference
│   └── ALGORITHM.md                 # deep-dive on every CV stage and its parameters
└── docker-compose.yml
```

> Note on the spec's flat `opencv/ svg/ api/` layout: they're nested under `backend/app/` here (`backend/app/opencv_pipeline`, `backend/app/svg`, `backend/app/api`) so they form an importable, testable Python package rather than loose top-level folders. The separation of concerns is identical - only the filesystem nesting differs. (`opencv_pipeline` rather than `opencv` avoids shadowing the real `cv2`/OpenCV import.)

## Installation

### Backend

Requires Python 3.10+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional - defaults work out of the box
uvicorn app.main:app --reload --port 8000
```

`scikit-image` (used only for the optional Sauvola threshold mode) is a normal entry in `requirements.txt`. If you deliberately omit it, everything else keeps working - requesting `threshold_mode: "sauvola"` just returns a clear `400` telling you to install it, instead of crashing.

### Frontend

Requires Node 18+.

```bash
cd frontend
npm install
cp .env.example .env               # optional - only needed for non-proxied deployments
npm run dev                        # http://localhost:5173
```

`npm run build` produces a static `dist/` bundle; `npm run lint` runs a strict `tsc --noEmit` check.

## Running with Docker

```bash
docker compose up --build
```

This builds and starts both services: the API on `:8000` and the frontend (served by nginx, which reverse-proxies `/api/*` to the backend container) on `:8080`.

## Using the app

1. **Upload** - drag & drop, or click to browse. PNG / JPEG / WEBP / BMP / TIFF are accepted.
2. **Tune parameters** (optional) - the left panel exposes every pipeline knob (blur, threshold mode, Canny, simplification tolerance, smoothing, convex hull, background removal, multi-object, output styling). Changes debounce and automatically re-run the pipeline.
3. **Inspect stages** - tabs flip between the original image, grayscale, blurred, threshold, edges, and the contour overlay, so you can see exactly why a given shape was detected.
4. **Inspect the SVG** - pan (drag), zoom (scroll wheel or buttons), reset, toggle vertex markers, and toggle an overlay of the original photo underneath the traced outline to visually verify alignment.
5. **Export** - download the SVG, the raw + normalized contour coordinates as JSON, or a rasterized PNG - all generated client-side from the same result, no extra server round-trip.

## API reference

Full request/response field documentation lives in [`docs/API.md`](docs/API.md) and is also available live (with a "try it out" UI) at `/docs` once the backend is running. Summary:

| Method | Path           | Purpose                                             |
|--------|----------------|------------------------------------------------------|
| GET    | `/api/health`  | Liveness probe                                       |
| GET    | `/api/formats` | Discover accepted file types/extensions and size limit |
| POST   | `/api/process` | Upload an image (+ optional JSON `params`), get back every pipeline stage, per-object geometry, and the final SVG |

## How the pipeline works

See [`docs/ALGORITHM.md`](docs/ALGORITHM.md) for the full explanation of every stage, every parameter, and the failure-fallback strategy. In short:

- **Auto Canny thresholds** are derived from the image's own median intensity (`edges.py::auto_canny_thresholds`), so a dim scan and an overexposed drone photo each get thresholds appropriate to their own contrast - no per-image tuning required.
- **Contour selection** filters by area ratio (both a minimum, to reject noise, and a maximum, to reject the well-known OpenCV edge case where a uniform image's own frame gets returned as a "contour").
- **Graceful fallbacks**: if the configured threshold/Canny combination finds nothing, the pipeline automatically retries with Otsu thresholding, then with contour extraction straight off the binary mask (skipping Canny). Only if all three attempts fail does the API return a `422` with an actionable message.

## Why coordinates are never hardcoded

Every coordinate that leaves the engine was computed from the pixels that were actually uploaded:

- Contours come from `cv2.findContours` on the mask/edge map that was itself derived from that image's own grayscale/threshold statistics.
- Simplification epsilon is expressed as a **fraction of that contour's own perimeter**, not an absolute pixel count - so the same default (`0.01`) behaves correctly on a 400px thumbnail and a 6000px drone photo alike.
- Normalization only ever **translates** points (subtracts one shared origin) and, for the 0-1 "normalized" variant, divides by **one shared scalar** (the larger side of the bounding box). Because x and y always move by the same factor, angles, aspect ratio, and relative proportions are mathematically preserved - never stretched or skewed.
- SVG coordinates use the same y-down convention as image pixels, so orientation is preserved with no flip/rotation logic to get wrong.

## Testing

```bash
cd backend
pytest tests/ -v
```

18 tests cover: geometric correctness on synthetic shapes (rectangles, rotated rectangles, triangles, multi-object scenes), aspect-ratio/orientation preservation, SVG well-formedness, both shape-type outputs, the blank-image fallback chain, and full HTTP-level API behaviour (success, validation, bad input, missing optional dependency).

Frontend: `npm run lint` (strict TypeScript check) and `npm run build` (production bundle) both run clean with zero errors.

## Examples

`examples/input/` contains one sample image per shape category named in the spec (site boundary, railway layout, floor plan, building outline, road layout, generic polygon); `examples/output/` contains the `.svg` and `.json` this engine produced for each, unedited. Regenerate them any time with:

```bash
python3 examples/generate_examples.py
```

## Limitations & extending the engine

This is a generic geometric pipeline, not a scene-understanding model - it traces contrast boundaries, it doesn't semantically know what a "railway" is. For best results the subject should have a reasonably distinguishable boundary against its background; the UI's parameter panel (especially threshold mode/invert and the Canny/blur controls) is there so you can adapt to a specific image's contrast without touching code. Ideas for taking it further:

- **Multi-object linking** - group nearby small contours (e.g. individual rail lines) into one logical object using clustering before simplification.
- **ML-based background/foreground segmentation** (e.g. `rembg`, a U²-Net model, or Segment Anything) as a drop-in replacement for the flood-fill `remove_background` step, wired in behind the same `PipelineConfig.remove_background` flag.
- **CAD/GIS export** - add a DXF or GeoJSON generator alongside `svg/generator.py`, reusing the same normalized point arrays.
- **Auth/rate limiting** - the API has no auth layer; put it behind your usual gateway before exposing it publicly.
- **Async/queued processing** - for very large batches, move `process_image` calls onto a task queue (e.g. Celery/RQ) instead of handling them inline in the request.
