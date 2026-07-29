"""Tests for turtlesim GUI command mapping."""

from my_py_pkg.turtle_gui_logic import velocity_for
import pytest


@pytest.mark.parametrize(
    ('action', 'expected'),
    [
        ('forward', (2.0, 0.0)),
        ('backward', (-2.0, 0.0)),
        ('left', (0.0, 2.0)),
        ('right', (0.0, -2.0)),
        ('stop', (0.0, 0.0)),
    ],
)
def test_velocity_for_known_action(action, expected):
    """A wrong speed or axis must fail for every supported action."""
    assert velocity_for(action) == expected


def test_velocity_for_rejects_unknown_action():
    """An unknown action must not silently create a movement command."""
    with pytest.raises(ValueError, match='Unknown turtle action'):
        velocity_for('jump')
