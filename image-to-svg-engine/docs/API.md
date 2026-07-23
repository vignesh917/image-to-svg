# API Reference

Base URL (local dev): `http://localhost:8000`. Interactive Swagger UI is always available at `/docs` (ReDoc at `/redoc`) directly from the running server, generated from the same Pydantic models documented below.

## `GET /api/health`

Liveness probe.

```json
{ "status": "ok", "service": "Image-to-SVG Extraction Engine" }
```

## `GET /api/formats`

Lets a client discover accepted formats/limits at runtime instead of hardcoding them.

```json
{
  "extensions": [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"],
  "content_types": ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp", "image/tiff", "image/x-tiff"],
  "max_upload_mb": 25
}
```

## `POST /api/process`

`multipart/form-data` with two parts:

| Field    | Type       | Required | Description                                                                 |
|----------|------------|----------|-------------------------------------------------------------------------------|
| `file`   | binary     | yes      | The image to process.                                                          |
| `params` | JSON string| no       | Any subset of the parameters below. Omitted fields use their documented default. |

### Parameters (`params`)

| Field                 | Type    | Default     | Range          | Description |
|-----------------------|---------|-------------|----------------|-------------|
| `blur_kernel`         | int     | `5`         | 1-31 (odd)     | Gaussian blur kernel size. `1` disables blur. |
| `threshold_mode`      | enum    | `"adaptive"`| adaptive / otsu / binary / sauvola | Binarization strategy. |
| `adaptive_block_size` | int     | `35`        | 3-199 (odd)    | Neighbourhood size for `adaptive`/`sauvola`. |
| `adaptive_c`          | int     | `5`         | -50-50         | Constant subtracted from the local mean (`adaptive` only). |
| `sauvola_k`           | float   | `0.2`       | 0.01-1.0       | Sauvola sensitivity constant (`sauvola` only; requires scikit-image). |
| `invert`              | bool    | `false`     | -              | Invert the binary mask (shape darker than background). |
| `morph_kernel`        | int     | `5`         | 0-31           | Morphological closing kernel; `0` disables it. |
| `canny_low`           | int     | `50`        | 0-500          | Canny lower threshold (ignored if `auto_canny`). |
| `canny_high`          | int     | `150`       | 0-500          | Canny upper threshold (ignored if `auto_canny`). |
| `auto_canny`          | bool    | `true`      | -              | Derive Canny thresholds from the image's own median intensity. |
| `epsilon_factor`      | float   | `0.01`      | 0.0001-0.2     | Douglas-Peucker epsilon, as a fraction of the contour's perimeter. |
| `smoothing`           | bool    | `false`     | -              | One pass of Chaikin corner-cutting before simplification. |
| `min_area_ratio`      | float   | `0.005`     | 0-1            | Discard contours smaller than this fraction of the image area. |
| `multi_object`        | bool    | `false`     | -              | Detect several objects instead of only the single largest. |
| `max_objects`         | int     | `1`         | 1-25           | Cap on returned objects when `multi_object` is true. |
| `use_convex_hull`     | bool    | `false`     | -              | Replace each contour with its convex hull before simplifying. |
| `remove_background`   | bool    | `false`     | -              | Flood-fill from the border to suppress a roughly uniform background first. |
| `shape_type`          | enum    | `"path"`    | path / polygon | Emit `<path>` or `<polygon>` elements. |
| `stroke_color`        | string  | `"#111827"` | any CSS color  | SVG stroke color. |
| `stroke_width`        | float   | `2.0`       | > 0            | SVG stroke width (user units). |
| `fill`                | string  | `"none"`    | any CSS color / `none` | SVG fill. |

### Response (`200 OK`)

```jsonc
{
  "success": true,
  "image_size": { "width": 1920, "height": 1080 },
  "stages": {
    "original": "data:image/png;base64,...",
    "grayscale": "data:image/png;base64,...",
    "blurred": "data:image/png;base64,...",
    "threshold": "data:image/png;base64,...",
    "edges": "data:image/png;base64,...",
    "contours_overlay": "data:image/png;base64,..."
  },
  "objects": [
    {
      "id": 0,
      "area": 152340.5,
      "perimeter": 1830.2,
      "raw_point_count": 812,
      "point_count": 6,
      "bounding_box": { "x": 120.0, "y": 84.0, "width": 640.0, "height": 410.0 },
      "points": [{ "x": 120.0, "y": 84.0 }, "..."],
      "points_normalized": [{ "x": 0.0, "y": 0.0 }, "..."],
      "points_svg": [{ "x": 12.8, "y": 8.4 }, "..."],
      "svg_path": "<path d=\"M12.8,8.4 L...\" fill=\"none\" stroke=\"#111827\" stroke-width=\"2\" stroke-linejoin=\"round\" />"
    }
  ],
  "svg": "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 665.6 425.7\" ...>...</svg>",
  "view_box": "0 0 665.60 425.70",
  "params_used": { "...": "the fully-resolved ProcessingParams, defaults included" }
}
```

`points` are in the original image's pixel space; `points_normalized` are scaled into 0-1 using a single shared scalar (so aspect ratio is preserved); `points_svg` are in the exact coordinate space used inside `svg_path`/`svg` (useful for overlaying markers on the rendered SVG, which is what the frontend's "show points" toggle does).

### Error responses

| Status | When                                                                 |
|--------|------------------------------------------------------------------------|
| `400`  | Empty/undecodable file, or a requested feature's optional dependency (e.g. scikit-image) isn't installed. |
| `413`  | File exceeds `MAX_UPLOAD_MB` (default 25MB).                          |
| `422`  | Params failed validation, or no boundary could be detected even after fallbacks. |
| `500`  | Unexpected server error (logged server-side; response body never leaks a stack trace). |

All error bodies share the same shape: `{ "success": false, "error"/"detail": "human-readable message" }`.
