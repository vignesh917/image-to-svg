#!/usr/bin/env python3
"""shape2svg CLI.

Examples:
  python cli.py photo.jpg                          # auto mode -> photo.svg
  python cli.py plan.png -o plan.svg --mode lines
  python cli.py site.jpg --mode regions --epsilon 0.01 --debug
  python cli.py site.jpg --geo 53.905,27.55,53.90,27.56   # + KML for My Maps
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shape2svg import PipelineConfig, process_file
from shape2svg.pipeline import render_overlay
from shape2svg.preprocess import load_image
from shape2svg.svg_out import build_kml


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Extract shapes/outlines from an image into SVG.")
    ap.add_argument("input", help="input image (jpg/png/...)")
    ap.add_argument("-o", "--output", help="output SVG path (default: <input>.svg)")
    ap.add_argument("--mode", choices=["auto", "regions", "lines"], default="auto")
    ap.add_argument("--max-dim", type=int, default=1200, help="processing resolution (default 1200)")
    ap.add_argument("--blur", type=int, default=None, help="Gaussian blur kernel (odd; default: auto)")
    # regions
    ap.add_argument("--threshold", choices=["otsu", "adaptive"], default="otsu")
    ap.add_argument("--invert", choices=["auto", "yes", "no"], default="auto", help="foreground polarity")
    ap.add_argument("--epsilon", type=float, default=0.005, help="region simplification (frac of perimeter)")
    ap.add_argument("--min-area", type=float, default=0.005, help="min region area (frac of image)")
    ap.add_argument("--max-regions", type=int, default=8)
    ap.add_argument("--hull", action="store_true", help="use convex hull of each region")
    ap.add_argument("--no-holes", action="store_true", help="ignore interior holes")
    # lines
    ap.add_argument("--line-source", choices=["auto", "canny", "threshold"], default="auto")
    ap.add_argument("--merge", type=int, default=None, help="edge-merging dilation kernel (default: auto)")
    ap.add_argument("--min-length", type=float, default=None, help="min polyline length, frac of diagonal (default: auto)")
    ap.add_argument("--line-epsilon", type=float, default=2.0, help="polyline simplification (px)")
    ap.add_argument("--max-paths", type=int, default=400)
    ap.add_argument("--no-join", action="store_true", help="disable junction joining of line segments")
    ap.add_argument("--join-angle", type=float, default=40.0, help="max continuation angle at junctions (deg)")
    # output
    ap.add_argument("--stroke-width", type=float, default=2.0)
    ap.add_argument("--stroke", default=None, help="single stroke color (default: palette per shape)")
    ap.add_argument("--json", action="store_true", help="also write extracted coordinates as JSON")
    ap.add_argument("--debug", action="store_true", help="also write an overlay PNG on the original")
    ap.add_argument("--geo", default=None, metavar="N,W,S,E",
                    help="lat/lng bounds of the imaged area -> also write a KML for Google My Maps")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    out = Path(args.output) if args.output else inp.with_suffix(".svg")

    cfg = PipelineConfig(
        mode=args.mode, max_dim=args.max_dim, blur_kernel=args.blur,
        threshold_mode=args.threshold,
        invert=None if args.invert == "auto" else (args.invert == "yes"),
        min_area_ratio=args.min_area, max_regions=args.max_regions,
        epsilon_frac=args.epsilon, use_hull=args.hull, include_holes=not args.no_holes,
        line_source=args.line_source, merge_kernel=args.merge,
        min_length_frac=args.min_length, line_epsilon_px=args.line_epsilon,
        max_paths=args.max_paths, join_segments=not args.no_join,
        join_angle_deg=args.join_angle,
        stroke_width=args.stroke_width, stroke=args.stroke,
    )

    result = process_file(str(inp), cfg)
    out.write_text(result.svg)
    print(f"wrote {out}  ({result.stats['n_regions']} regions, "
          f"{result.stats['n_polylines']} polylines, mode={result.mode})")
    print(json.dumps(result.stats, indent=2))

    if args.json:
        jp = out.with_suffix(".json")
        jp.write_text(result.json)
        print(f"wrote {jp}")
    if args.debug:
        import cv2
        op = out.with_name(out.stem + "_overlay.png")
        cv2.imwrite(str(op), render_overlay(load_image(str(inp)), result))
        print(f"wrote {op}")
    if args.geo:
        try:
            n, w_, s, e = (float(v) for v in args.geo.split(","))
        except ValueError:
            print("--geo expects north,west,south,east (decimal degrees)", file=sys.stderr)
            return 2
        kp = out.with_suffix(".kml")
        kp.write_text(build_kml(result.width, result.height, (n, w_, s, e),
                                result.regions, result.polylines, name=inp.stem))
        print(f"wrote {kp}  (import into Google My Maps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
