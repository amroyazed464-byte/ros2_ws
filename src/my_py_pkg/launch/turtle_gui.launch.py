"""Launch Turtlesim and the PyQt5 control panel together."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Return the two-node GUI demonstration."""
    return LaunchDescription([
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            name='turtlesim',
            output='screen',
        ),
        Node(
            package='my_py_pkg',
            executable='turtle_gui',
            name='turtle_gui_controller',
            output='screen',
        ),
    ])
