"""shape2svg — dynamic shape/outline extraction from images to SVG.

No per-image logic: pixels in, parameters in, geometry out.
"""
from shape2svg.pipeline import PipelineConfig, ExtractionResult, process_image, process_file

__version__ = "1.0.0"
__all__ = ["PipelineConfig", "ExtractionResult", "process_image", "process_file"]
