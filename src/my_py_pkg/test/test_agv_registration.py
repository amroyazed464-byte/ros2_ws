"""Package registration checks for ROS 2 homework seven."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_agv_executables_are_registered():
    setup_source = (PACKAGE_ROOT / 'setup.py').read_text(encoding='utf-8')
    assert 'agv_commander = my_py_pkg.agv_commander:main' in setup_source
    assert (
        'charging_station = my_py_pkg.charging_station:main'
        in setup_source
    )


def test_nav2_simple_commander_dependency_is_declared():
    package_xml = (PACKAGE_ROOT / 'package.xml').read_text(encoding='utf-8')
    assert '<depend>nav2_simple_commander</depend>' in package_xml


def test_direct_nav2_action_dependency_is_declared():
    package_xml = (PACKAGE_ROOT / 'package.xml').read_text(encoding='utf-8')
    assert '<depend>nav2_msgs</depend>' in package_xml
