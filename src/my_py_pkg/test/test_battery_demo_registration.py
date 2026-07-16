"""Console script registration tests for the battery demonstration."""

from pathlib import Path


def test_all_battery_demo_nodes_are_registered():
    """All three new nodes are available through ros2 run."""
    setup_source = (
        Path(__file__).resolve().parents[1] / 'setup.py'
    ).read_text(encoding='utf-8')
    assert 'battery = my_py_pkg.battery:main' in setup_source
    assert 'led_panel = my_py_pkg.led_panel:main' in setup_source
    assert (
        'turtle_controller = my_py_pkg.turtle_controller:main'
        in setup_source
    )
