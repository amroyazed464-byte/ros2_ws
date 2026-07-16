"""Pure state transitions shared by the battery demonstration nodes."""


def next_battery_state(
    level: int, charging: bool, step: int
) -> tuple[int, bool]:
    """Advance one battery tick and reverse direction at a boundary."""
    next_level = level + step if charging else level - step
    next_level = max(0, min(100, next_level))
    if next_level == 0:
        return next_level, True
    if next_level == 100:
        return next_level, False
    return next_level, charging


def next_led3_state(level: int, led3_on: bool) -> bool:
    """Latch LED 3 on at empty and off only after reaching full charge."""
    bounded_level = max(0, min(100, level))
    if bounded_level == 0:
        return True
    if bounded_level == 100:
        return False
    return led3_on


def target_for_led3(value: int) -> tuple[float, float, float]:
    """Return the turtlesim target associated with a binary LED value."""
    if value == 1:
        return 11.0, 11.0, 0.0
    if value == 0:
        return 5.5, 5.5, 0.0
    raise ValueError('LED 3 value must be 0 or 1')
