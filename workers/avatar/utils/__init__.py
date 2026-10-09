"""LiveTalking utility package.

Keeping this an explicit package prevents optional model dependencies from
claiming the generic top-level ``utils`` name before the avatar runtime imports
its logger, image, and device helpers.
"""
