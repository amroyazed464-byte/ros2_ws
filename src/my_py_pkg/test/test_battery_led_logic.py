"""Unit tests for battery, LED, and turtle target state logic."""

from my_py_pkg.battery_logic import (
    next_battery_state,
    next_led3_state,
    target_for_led3,
)
import pytest


def test_battery_reverses_to_charging_at_empty():
    """A discharging battery starts charging when it reaches zero."""
    assert next_battery_state(10, False, 10) == (0, True)


def test_battery_reverses_to_discharging_at_full():
    """A charging battery starts discharging when it reaches full."""
    assert next_battery_state(90, True, 10) == (100, False)


def test_battery_clamps_oversized_steps():
    """Battery steps never move the level beyond its valid range."""
    assert next_battery_state(5, False, 10) == (0, True)
    assert next_battery_state(95, True, 10) == (100, False)


def test_led3_latches_from_empty_until_full():
    """LED 3 stays on for the complete charging phase."""
    assert next_led3_state(0, False) is True
    assert next_led3_state(50, True) is True
    assert next_led3_state(100, True) is False


def test_turtle_target_matches_binary_led_value():
    """Binary LED states map to the requested turtlesim coordinates."""
    assert target_for_led3(1) == (11.0, 11.0, 0.0)
    assert target_for_led3(0) == (5.5, 5.5, 0.0)


def test_turtle_target_rejects_non_binary_value():
    """Only well-formed binary LED values select a target."""
    with pytest.raises(ValueError, match='LED 3 value must be 0 or 1'):
        target_for_led3(2)
