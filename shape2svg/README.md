# shape2svg — dynamic shape extraction from images

Give it any image and it recreates the shape/layout as a clean SVG. There is no per-image logic anywhere in the codebase: the same code path handles a site boundary, a floor plan, a railway yard photo, or an arbitrary polygon. Behaviour is a pure function of pixels in + parameters in.

```
image ─→ analyze (auto-detect) ─→ regions mode: blur → threshold (auto polarity)
                               │                → morphology → contours (+holes)
                               │                → Douglas-Peucker → polygons
                               │
                               └→ lines mode:   blur → auto-Canny (or threshold for
                                                drawings) → texture merge → skeletonize
                                                → graph trace → junction joining
                                                → Douglas-Peucker → polylines
                                        ─→ SVG (viewBox = original image, exact proportions)
                                        ─→ JSON coordinates / KML for Google My Maps
```

## Quickstart

```bash
pip install -r requirements.txt

# CLI — one command per image
python cli.py examples/ref1.jpg                 # auto mode → examples/ref1.svg
python cli.py plan.png --mode lines             # force a mode
python cli.py site.jpg --debug --json           # + overlay PNG + coordinates JSON
python cli.py site.jpg --geo 53.91,27.54,53.90,27.56   # + KML → import into Google My Maps

# Web app — drag & drop, live parameter tuning, overlay verification
python server.py                                # open http://localhost:8000

# Tests — synthetic images the pipeline has never seen
python -m pytest tests/ -q
```

## Why it generalises (not a manual trace)

Every stage derives its numbers from the image itself:

- **Mode auto-detect** (`autodetect.py`): a near-binary histogram means a drawing/scan; high Canny edge density means a texture-rich photo (→ line network); otherwise the skeleton-to-foreground "thinness" ratio separates solid shapes (→ region outlines) from stroke content (→ lines). The decision and its reason are reported in the output stats.
- **Threshold** is Otsu (image histogram), **Canny** thresholds come from the image median, and **polarity** is auto: whichever class owns the image border is background — works even when the shape covers more than half the frame.
- **Parameter presets** (blur / texture-merge / minimum line length) are selected from the measured edge density, and every one can be overridden by a flag or a UI slider.
- **Coordinates** are contour/skeleton pixels on the original image grid. The SVG `viewBox` equals the source image dimensions, so proportions, aspect ratio and alignment are preserved exactly. Nothing is ever normalised, stretched or hand-placed.

## The two modes

**regions** — closed boundaries. Threshold → external contours with holes (`RETR_CCOMP`) → area filter → Douglas-Peucker simplification (ε as a fraction of perimeter). Output: `<path>` polygons with `fill-rule="evenodd"` so interior holes render correctly. Suits site boundaries, filled shapes, blobs, lakes.

**lines** — open curve networks. For drawings, the thresholded strokes are skeletonized directly; for photos, auto-Canny edges are dilated so each track/road's texture merges into one band, then skeletonized to its centerline. The skeleton is traced into polylines with a graph walk (endpoints/junctions as nodes), and segments that continue smoothly through a junction (within an angular tolerance) are joined into long paths — this is what turns a railway crossing from confetti into continuous track lines. Suits railway yards, roads, walls, wireframes.

## Results on the reference images

`examples/` contains both reference aerial photos plus generated outputs: the SVGs, coordinate JSONs, overlay verification PNGs (extracted geometry drawn on the original), and a synthetic site-boundary demo with KML.

- `ref1.jpg` (railway yard, texture-rich): auto-detect → lines (edge density 0.17), 52 polylines tracing tracks, platforms, buildings and trains.
- `ref2.jpg` (parallel tracks): auto-detect → lines, 29 polylines along the tracks.
- `demo_site.png` (synthetic boundary): auto-detect → regions, recovers all 7 polygon vertices to within ~1 px.

## Verification

`tests/test_engine.py` builds synthetic images at runtime and asserts: star boundary IoU > 0.97, donut hole preserved with IoU > 0.95, floor-plan drawing auto-routes to lines and recovers the wall network length, viewBox always matches source dimensions, all coordinates in bounds, JSON roundtrip. The web UI's **Overlay check** tab and the CLI `--debug` flag render the extracted geometry over the original photo for visual accuracy checks.

## Outputs

- `.svg` — `viewBox` = image size; regions as filled `<path>` elements, lines as stroked open `<path>` elements; one palette colour per shape.
- `.json` (`--json`) — every polygon/polyline as pixel coordinates, for downstream use.
- `.kml` (`--geo N,W,S,E`) — pixel→lat/lng mapped over the supplied bounds of the imaged area; import directly into Google My Maps to plot the layout at real-world location and scale.

## Key parameters

| flag / slider | default | effect |
|---|---|---|
| `--mode` | auto | `regions`, `lines`, or auto-detect |
| `--epsilon` | 0.005 | region simplification (fraction of perimeter); higher = fewer points |
| `--min-area` | 0.005 | drop regions smaller than this fraction of the image |
| `--min-length` | auto | drop polylines shorter than this fraction of the diagonal |
| `--merge` | auto | edge-merge kernel; higher fuses more texture into one line |
| `--blur` | auto | pre-blur; higher suppresses more texture |
| `--join-angle` | 40° | max direction change for joining lines across junctions |
| `--invert` | auto | foreground polarity override |
| `--max-dim` | 1200 | processing resolution (output stays at original resolution) |

## Project structure

```
shape2svg/
  shape2svg/            the engine (importable, framework-free)
    preprocess.py       load, resize, blur, auto-polarity threshold, auto-Canny
    autodetect.py       regions-vs-lines decision from image statistics
    regions.py          contours + holes + simplification
    lines.py            skeleton tracing + junction joining
    svg_out.py          SVG / JSON / KML generation
    pipeline.py         orchestrator + config + overlay renderer
  cli.py                command-line tool
  server.py             FastAPI app (POST /api/extract)
  static/index.html     web UI (drag & drop, sliders, overlay tab, downloads)
  tests/test_engine.py  synthetic generalisation tests
  examples/             reference images + generated outputs
```

## Limitations

Thresholding on busy photos is approximate — the pipeline extracts the dominant visual structure, not semantic objects (it cannot know that a train is not a track). Dense parallel lines closer than the merge kernel may fuse. For photos, line-mode accuracy is bounded by edge contrast; the sliders exist to trade coverage against noise, live in the UI.
