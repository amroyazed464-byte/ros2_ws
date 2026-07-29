"""Pure velocity mapping for the turtlesim GUI."""


VELOCITIES = {
    'forward': (2.0, 0.0),
    'backward': (-2.0, 0.0),
    'left': (0.0, 2.0),
    'right': (0.0, -2.0),
    'stop': (0.0, 0.0),
}


def velocity_for(action: str) -> tuple[float, float]:
    """Return linear x and angular z velocities for an action."""
    try:
        return VELOCITIES[action]
    except KeyError as error:
        raise ValueError(f'Unknown turtle action: {action}') from error
