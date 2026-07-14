"""Static registration checks for the turtle summoner node."""

from pathlib import Path


def test_turtle_summoner_console_script_is_registered():
    """The package exposes the required turtle_summoner executable."""
    setup_py = Path(__file__).resolve().parents[1] / 'setup.py'

    assert 'turtle_summoner = my_py_pkg.turtle_summoner:main' in setup_py.read_text(
        encoding='utf-8'
    )


def test_turtle_summoner_checks_the_spawn_response_name_before_succeeding():
    """A spawn only succeeds after turtlesim confirms the requested name."""
    module = (
        Path(__file__).resolve().parents[1] / 'my_py_pkg' / 'turtle_summoner.py'
    ).read_text(encoding='utf-8')

    assert 'spawn_response = await self._spawn_client.call_async(request)' in module
    assert 'spawn_response.name != turtle_name' in module


def test_turtle_summoner_reserves_each_operation_before_awaiting_ros():
    """Concurrent requests cannot both pass the local spawned-state check."""
    module = (
        Path(__file__).resolve().parents[1] / 'my_py_pkg' / 'turtle_summoner.py'
    ).read_text(encoding='utf-8')

    assert 'self._operation_lock = Lock()' in module
    assert 'self._operation_pending' in module
    assert 'finally:' in module


def test_turtle_summoner_reads_double_parameters_without_value_property():
    """Use the explicit ROS parameter message field for x and y."""
    module = (
        Path(__file__).resolve().parents[1] / 'my_py_pkg' / 'turtle_summoner.py'
    ).read_text(encoding='utf-8')

    assert "get_parameter('x').get_parameter_value().double_value" in module
    assert "get_parameter('y').get_parameter_value().double_value" in module
    assert "get_parameter('turtle_name').get_parameter_value().string_value" in module


def test_turtle_summoner_does_not_shadow_node_parameter_storage():
    """Do not reuse Node's internal _parameters dictionary name for a method."""
    module = (
        Path(__file__).resolve().parents[1] / 'my_py_pkg' / 'turtle_summoner.py'
    ).read_text(encoding='utf-8')

    assert 'def _read_parameters(' in module
    assert 'self._read_parameters()' in module
    assert 'def _parameters(' not in module
