# Pipeline deep-dive

This document explains every stage in `backend/app/opencv_pipeline/` and `backend/app/svg/generator.py`, in the order they actually execute (see `pipeline.py::process_image`).

## 1. Decode (format-agnostic)

`utils/image_io.py::decode_image` uses Pillow (not `cv2.imdecode`) so PNG, JPEG, WEBP, BMP, and TIFF are all handled uniformly, including EXIF-rotated phone/drone photos (`ImageOps.exif_transpose`) and palette/CMYK images (forced to RGB before converting to OpenCV's BGR).

## 2. Grayscale

`preprocessing.py::to_grayscale` - a single `cv2.cvtColor` call. Every later stage operates on one channel.

## 3. Optional background suppression (bonus feature)

If `remove_background=true`, `preprocessing.py::remove_background` flood-fills inward from the image's border midpoints and corners, producing a soft foreground mask that gets AND-ed with the grayscale image. This is model-free and conservative by design: it assumes only that the frame's edges are background (true for most top-down/aerial or tabletop-scan shots), not that it knows what the subject is.

## 4. Denoise + Gaussian blur

`preprocessing.py::denoise` (light `fastNlMeansDenoising`, skipped above 2000px on the longest side purely for latency) followed by `gaussian_blur`. This suppresses high-frequency texture (roof tiles, gravel, JPEG artifacts) that would otherwise fragment the Canny edge map into thousands of disconnected micro-edges.

## 5. Threshold -> binary image

Four interchangeable strategies (`threshold_mode`), all producing a 0/255 mask:

- **`adaptive`** (default) - `cv2.adaptiveThreshold` with a Gaussian-weighted local mean. Robust to gradual illumination changes.
- **`sauvola`** - `skimage.filters.threshold_sauvola`. Generally outperforms plain adaptive mean thresholding on photographs with strong *local* contrast swings (e.g. an aerial shot half in sun, half in shadow). Optional dependency - see below.
- **`otsu`** - a single global threshold chosen automatically from the image's bimodal histogram. Fast and reliable for evenly-lit scans/renders.
- **`binary`** - a fixed cutoff (127). Useful for inputs that are already near-binary.

A small morphological opening (`morphological_open`) follows, removing speckle noise before contour search.

## 6. Canny edge detection (auto-thresholded)

`edges.py::auto_canny_thresholds` computes `low = (1-σ)·median`, `high = (1+σ)·median` (σ=0.33) from the binary mask's own pixel statistics, so a dim image and a bright image each get sensible thresholds without any manual tuning. This is the single biggest reason the same code works unmodified on a brand-new image tomorrow. Manual thresholds remain available (`auto_canny=false` + `canny_low`/`canny_high`) for edge cases.

## 7. Morphological closing

Bridges small gaps in the edge map (`morph_kernel`, default 5) so a boundary broken up by noise or partial occlusion reconnects into a single traceable contour before `findContours` runs.

## 8. Contour detection

`contours.py::find_all_contours` - `cv2.findContours(..., cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)`. `RETR_EXTERNAL` is a deliberate choice: for boundary/outline extraction we want each object's outermost silhouette, not internal holes or nested detail.

## 9. Contour selection (with safety bounds)

`select_significant_contours` keeps only contours whose area is between `min_area_ratio` and `max_area_ratio` (0.97, not user-configurable) of the total image area, then keeps the largest `max_objects` of what remains.

The upper bound exists to neutralize a well-known OpenCV edge case: on a uniform/blank image (or a mask that touches every border), `findContours` can return the image's own outer frame as if it were a detected shape. That contour carries zero real information, so it's treated identically to "nothing found" rather than returned as a false-positive rectangle.

## 10. Fallback chain

If step 9 finds nothing:

1. **Retry with Otsu** thresholding regardless of the configured mode (handles images with unexpectedly flat or noisy lighting).
2. **Retry by finding contours directly on the binary mask**, skipping Canny entirely (handles masks whose boundary is clean but doesn't survive edge detection well).
3. If still nothing, raise `PipelineError` -> the API returns `422` with an actionable message, rather than a blank/garbage result.

## 11. Optional convex hull / smoothing

- `use_convex_hull` replaces the raw point set with `cv2.convexHull` - useful when you want a clean envelope (e.g. a property/site boundary) rather than every concave detail of the traced edge.
- `smoothing` applies one pass of **Chaikin's corner-cutting algorithm** (`chaikin_smooth`) before simplification, softening jagged pixel-level noise on the contour.

## 12. Douglas-Peucker simplification

`contours.py::douglas_peucker` wraps `cv2.approxPolyDP`. Critically, `epsilon` is computed as `epsilon_factor * contour_perimeter`, **not** an absolute pixel value - so the same default (`0.01`, i.e. 1% of the perimeter) simplifies a 400px thumbnail and a 6000px drone photo to a comparable level of visual fidelity.

## 13. Normalization (shape/angle/scale/aspect-ratio preserving)

`normalize.py` is intentionally minimal:

- `bounding_box_of` / `union_bounding_box` compute the (union) bounding box of the selected object(s).
- `translate_to_origin` subtracts one shared `(x, y)` origin from every point - a pure translation.
- `normalize_unit` divides every point by **one shared scalar** (the larger side of the bounding box) - a pure, uniform scale.

Because x and y are always transformed by the *same* factor, angles, aspect ratio, and relative proportions between vertices are mathematically unchanged. There is no independent x/y stretching anywhere in the codebase, which is what would distort a shape.

Orientation needs no special handling: SVG's coordinate system is y-down, identical to image pixel coordinates, so a direct coordinate copy already matches what a human sees in the source image - no flips or axis inversions to get wrong.

## 14. SVG generation

`svg/generator.py` hand-builds the output (no external SVG library needed for something this structurally simple):

- `points_to_path_d` / `points_to_polygon_points` render `<path d="M x,y L x,y ... Z">` or `<polygon points="x,y x,y ...">`.
- `build_svg_document` wraps one or more shape fragments in a single `<svg>` whose `viewBox`/`width`/`height` exactly match the (padded) bounding box of the detected geometry - so the output auto-fits its content at any render size, with correct aspect ratio, by construction.
- Multiple detected objects (`multi_object=true`) are each assigned a distinct color from a fixed palette so they stay visually distinguishable in the combined SVG.

## Parameter tuning cheat-sheet

| Input looks like...                              | Try |
|---------------------------------------------------|-----|
| Aerial/drone photo, uneven sun/shadow (railway yard, site boundary) | `threshold_mode="sauvola"`, moderate `blur_kernel` (5-9), `morph_kernel` 5-9 to bridge gaps between rails/gravel texture |
| Clean CAD export / floor plan scan, flat lighting | `threshold_mode="otsu"`, small `blur_kernel` (1-3), lower `epsilon_factor` (0.005) for crisp corners |
| Line drawing on white paper (dark lines on light background) | `threshold_mode="binary"`, `invert=true` if lines are darker than the fill |
| Shape occupies almost the whole frame with little margin | Lower `min_area_ratio` slightly if it's being rejected as noise; crop the photo tighter if possible |
| Want a smooth property-boundary style outline rather than every jagged pixel-edge detail | `use_convex_hull=true` and/or `smoothing=true`, higher `epsilon_factor` |
| Multiple buildings/lots in one image | `multi_object=true`, set `max_objects` to the expected count |
