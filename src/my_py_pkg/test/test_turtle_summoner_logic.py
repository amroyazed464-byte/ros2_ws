from my_py_pkg.turtle_summoner_logic import validate_position


def test_validate_position_rejects_bool_and_int_coordinates():
    assert validate_position(True, 3.8) == (False, 'x must be a float')
    assert validate_position(7, 3.8) == (False, 'x must be a float')
    assert validate_position(7.3, False) == (False, 'y must be a float')
    assert validate_position(7.3, 3) == (False, 'y must be a float')


def test_validate_position_accepts_turtlesim_bounds():
    assert validate_position(7.3, 3.8) == (True, '')
    assert validate_position(1.0, 1.0) == (True, '')
    assert validate_position(10.0, 10.0) == (True, '')


def test_validate_position_rejects_non_finite_or_out_of_bounds_values():
    assert validate_position(float('nan'), 3.8) == (False, 'x must be finite')
    assert validate_position(7.3, float('nan')) == (False, 'y must be finite')
    assert validate_position(float('inf'), 3.8) == (False, 'x must be finite')
    assert validate_position(float('-inf'), 3.8) == (False, 'x must be finite')
    assert validate_position(7.3, float('inf')) == (False, 'y must be finite')
    assert validate_position(7.3, float('-inf')) == (False, 'y must be finite')
    assert validate_position(0.5, 3.8) == (False, 'x must be between 1.0 and 10.0')
    assert validate_position(7.3, 10.5) == (False, 'y must be between 1.0 and 10.0')
