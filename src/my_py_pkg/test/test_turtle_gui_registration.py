"""Package registration tests for the turtlesim GUI."""

import importlib.util
import os
from pathlib import Path
import runpy
from unittest.mock import patch
import xml.etree.ElementTree as ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_setup_registers_gui_and_installs_launch_file(monkeypatch):
    """A missing executable entry or installed launch file must fail."""
    monkeypatch.chdir(PACKAGE_ROOT)
    with patch('setuptools.setup') as setup_mock:
        runpy.run_path(str(PACKAGE_ROOT / 'setup.py'), run_name='__main__')

    setup_arguments = setup_mock.call_args.kwargs
    console_scripts = setup_arguments['entry_points']['console_scripts']
    assert 'turtle_gui = my_py_pkg.turtle_gui:main' in console_scripts

    launch_destination = os.path.join(
        'share',
        'my_py_pkg',
        'launch',
    )
    launch_files = [
        sources
        for destination, sources in setup_arguments['data_files']
        if destination == launch_destination
    ]
    assert len(launch_files) == 1
    assert [Path(source).name for source in launch_files[0]] == [
        'turtle_gui.launch.py'
    ]


def test_manifest_declares_gui_runtime_dependencies():
    """Missing ROS2, Turtlesim, Launch, or Qt dependencies must fail."""
    root = ElementTree.parse(PACKAGE_ROOT / 'package.xml').getroot()
    dependencies = {
        element.text
        for tag in ('depend', 'exec_depend')
        for element in root.findall(tag)
    }
    assert {
        'geometry_msgs',
        'launch',
        'launch_ros',
        'python3-pyqt5',
        'rclpy',
        'turtlesim',
    } <= dependencies


def test_launch_description_starts_turtlesim_and_gui():
    """The launch description must contain both required ROS2 nodes."""
    launch_path = (
        PACKAGE_ROOT / 'launch' / 'turtle_gui.launch.py'
    )
    spec = importlib.util.spec_from_file_location(
        'turtle_gui_launch',
        launch_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    nodes = module.generate_launch_description().entities
    executables = {
        (node.node_package, node.node_executable)
        for node in nodes
    }
    assert executables == {
        ('my_py_pkg', 'turtle_gui'),
        ('turtlesim', 'turtlesim_node'),
    }
