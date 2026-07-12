"""ROS-independent helpers used by the turtle square nodes."""

import math


def angle_error(target: float, current: float) -> float:
    """Return the shortest signed angular difference in radians."""
    difference = target - current
    return math.atan2(math.sin(difference), math.cos(difference))


def corner_from_origin(
    origin_x: float, origin_y: float, side_length: float, corner_index: int
) -> tuple[float, float]:
    """Return one counter-clockwise square corner, starting at the origin."""
    corners = (
        (origin_x + side_length, origin_y),
        (origin_x + side_length, origin_y + side_length),
        (origin_x, origin_y + side_length),
        (origin_x, origin_y),
    )
    return corners[corner_index % len(corners)]


def parse_side_length(text: str) -> float | None:
    """Parse a finite, strictly positive side length from terminal input."""
    try:
        side_length = float(text.strip())
    except ValueError:
        return None

    if not math.isfinite(side_length) or side_length <= 0.0:
        return None
    return side_length
