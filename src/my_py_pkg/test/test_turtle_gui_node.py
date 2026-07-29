"""ROS integration tests for the turtlesim GUI node."""

import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from my_py_pkg.turtle_gui import TurtleGuiNode


def test_node_publishes_forward_twist_and_detects_subscriber():
    """A wrong node, topic, message type, or speed must fail this test."""
    rclpy.init()
    controller = TurtleGuiNode()
    listener = Node('turtle_gui_test_listener')
    received = []
    subscription = listener.create_subscription(
        Twist,
        '/turtle1/cmd_vel',
        received.append,
        10,
    )
    executor = SingleThreadedExecutor()
    executor.add_node(controller)
    executor.add_node(listener)

    try:
        assert controller.get_name() == 'turtle_gui_controller'
        deadline = time.monotonic() + 3.0
        while (
            not controller.has_turtlesim()
            and time.monotonic() < deadline
        ):
            executor.spin_once(timeout_sec=0.05)
        assert controller.has_turtlesim()

        assert controller.publish_action('forward') == (2.0, 0.0)
        deadline = time.monotonic() + 3.0
        while not received and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        assert received
        assert received[-1].linear.x == 2.0
        assert received[-1].angular.z == 0.0
    finally:
        listener.destroy_subscription(subscription)
        executor.remove_node(listener)
        executor.remove_node(controller)
        listener.destroy_node()
        controller.destroy_node()
        executor.shutdown()
        rclpy.shutdown()
