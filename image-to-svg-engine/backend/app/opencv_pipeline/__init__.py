"""Computer-vision pipeline: image in, simplified contours out.

Every function in this package is generic - it takes pixels and parameters
and returns pixels/points. Nothing references a specific image, filename,
or shape category, which is what makes the pipeline reusable for any future
upload without code changes.
"""
