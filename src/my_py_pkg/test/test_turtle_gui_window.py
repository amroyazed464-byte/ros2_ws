"""Offscreen interaction tests for the PyQt5 turtle controller."""

import os
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from geometry_msgs.msg import Twist
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from my_py_pkg.turtle_gui import TurtleControlWindow, TurtleGuiNode


@pytest.fixture(scope='module')
def app():
    """Provide the single QApplication allowed by Qt."""
    return QApplication.instance() or QApplication([])


def _spin_until(executor, predicate, timeout=3.0):
    """Spin real ROS nodes until an observable condition becomes true."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)
    return predicate()


def test_controls_and_close_publish_expected_twists(app):
    """Wrong button, key, speed, topic, or missing close-stop must fail."""
    rclpy.init()
    controller = TurtleGuiNode()
    listener = Node('turtle_gui_window_test_listener')
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
    window = TurtleControlWindow(controller)
    window.show()
    app.processEvents()

    try:
        assert _spin_until(executor, controller.has_turtlesim)

        forward = window.findChild(QPushButton, 'forward_button')
        assert forward is not None
        QTest.mouseClick(forward, Qt.LeftButton)
        assert _spin_until(executor, lambda: len(received) >= 1)
        assert received[-1].linear.x == 2.0
        assert received[-1].angular.z == 0.0
        assert window.linear_value.text() == '2.0 m/s'
        assert window.angular_value.text() == '0.0 rad/s'

        QTest.keyClick(window, Qt.Key_Left)
        assert _spin_until(executor, lambda: len(received) >= 2)
        assert received[-1].linear.x == 0.0
        assert received[-1].angular.z == 2.0

        QTest.keyClick(window, Qt.Key_Space)
        assert _spin_until(executor, lambda: len(received) >= 3)
        assert received[-1].linear.x == 0.0
        assert received[-1].angular.z == 0.0

        window.close()
        assert _spin_until(executor, lambda: len(received) >= 4)
        assert received[-1].linear.x == 0.0
        assert received[-1].angular.z == 0.0
    finally:
        window.close()
        listener.destroy_subscription(subscription)
        executor.remove_node(listener)
        executor.remove_node(controller)
        listener.destroy_node()
        controller.destroy_node()
        executor.shutdown()
        rclpy.shutdown()


def test_connection_status_tracks_real_subscriber(app):
    """The status must change when a real cmd_vel subscriber appears."""
    rclpy.init()
    controller = TurtleGuiNode()
    executor = SingleThreadedExecutor()
    executor.add_node(controller)
    window = TurtleControlWindow(controller)
    listener = None

    try:
        window.refresh_connection_status()
        assert window.connection_status.text() == '等待 Turtlesim'
        assert (
            window.connection_status.property('connectionState')
            == 'waiting'
        )

        listener = Node('turtle_gui_status_test_listener')
        listener.create_subscription(
            Twist,
            '/turtle1/cmd_vel',
            lambda message: None,
            10,
        )
        executor.add_node(listener)
        assert _spin_until(executor, controller.has_turtlesim)
        window.refresh_connection_status()
        assert window.connection_status.text() == '已连接'
        assert (
            window.connection_status.property('connectionState')
            == 'online'
        )
    finally:
        window.close()
        if listener is not None:
            executor.remove_node(listener)
            listener.destroy_node()
        executor.remove_node(controller)
        controller.destroy_node()
        executor.shutdown()
        rclpy.shutdown()
