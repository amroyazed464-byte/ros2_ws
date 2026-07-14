"""ROS-independent validation helpers for turtle summoning."""

import math


def validate_position(x: float, y: float) -> tuple[bool, str]:
    """Validate a turtlesim visible-area coordinate pair."""
    if not math.isfinite(x):
        return False, 'x must be finite'
    if not math.isfinite(y):
        return False, 'y must be finite'
    if not 1.0 <= x <= 10.0:
        return False, 'x must be between 1.0 and 10.0'
    if not 1.0 <= y <= 10.0:
        return False, 'y must be between 1.0 and 10.0'
    return True, ''
