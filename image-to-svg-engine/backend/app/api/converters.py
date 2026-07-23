"""Glue between the pydantic API schema and the framework-agnostic pipeline
dataclasses. Kept separate so neither side needs to know about the other."""
from __future__ import annotations

from app.models.schemas import BoundingBox as BoundingBoxSchema
from app.models.schemas import DetectedObject, Point, ProcessingParams
from app.opencv_pipeline.pipeline import DetectedObjectResult, PipelineConfig


def params_to_config(params: ProcessingParams) -> PipelineConfig:
    return PipelineConfig(
        blur_kernel=params.blur_kernel,
        threshold_mode=params.threshold_mode,
        adaptive_block_size=params.adaptive_block_size,
        adaptive_c=params.adaptive_c,
        sauvola_k=params.sauvola_k,
        invert=params.invert,
        morph_kernel=params.morph_kernel,
        canny_low=params.canny_low,
        canny_high=params.canny_high,
        auto_canny=params.auto_canny,
        epsilon_factor=params.epsilon_factor,
        smoothing=params.smoothing,
        min_area_ratio=params.min_area_ratio,
        multi_object=params.multi_object,
        max_objects=params.max_objects,
        use_convex_hull=params.use_convex_hull,
        remove_background=params.remove_background,
        shape_type=params.shape_type,
        stroke_color=params.stroke_color,
        stroke_width=params.stroke_width,
        fill=params.fill,
    )


def object_result_to_schema(result: DetectedObjectResult) -> DetectedObject:
    return DetectedObject(
        id=result.id,
        area=result.area,
        perimeter=result.perimeter,
        raw_point_count=result.raw_point_count,
        point_count=result.point_count,
        bounding_box=BoundingBoxSchema(
            x=result.bounding_box.x,
            y=result.bounding_box.y,
            width=result.bounding_box.width,
            height=result.bounding_box.height,
        ),
        points=[Point(x=float(p[0]), y=float(p[1])) for p in result.points],
        points_normalized=[Point(x=float(p[0]), y=float(p[1])) for p in result.points_normalized],
        points_svg=[Point(x=float(p[0]), y=float(p[1])) for p in result.points_svg],
        svg_path=result.svg_fragment,
    )
