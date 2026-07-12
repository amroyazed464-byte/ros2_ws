import math

from my_py_pkg.square_control import angle_error, corner_from_origin, parse_side_length


def test_angle_error_wraps_across_pi():
    assert abs(angle_error(-3.13, 3.13)) < 0.03


def test_corner_from_origin_returns_the_third_square_vertex():
    assert corner_from_origin(1.0, 2.0, 2.0, 2) == (1.0, 4.0)


def test_parse_side_length_accepts_positive_finite_value():
    assert parse_side_length('2.5') == 2.5


def test_parse_side_length_rejects_invalid_values():
    assert parse_side_length('0') is None
    assert parse_side_length('-1') is None
    assert parse_side_length('nan') is None
    assert parse_side_length('side') is None
    assert parse_side_length(str(math.inf)) is None
