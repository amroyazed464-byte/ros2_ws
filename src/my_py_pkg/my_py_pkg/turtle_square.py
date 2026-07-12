#!/usr/bin/env python3
"""Draw one feedback-controlled turtlesim square for each requested side length."""

import math
from enum import Enum, auto

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float32
from turtlesim.msg import Pose

from my_py_pkg.square_control import angle_error, corner_from_origin


class MotionState(Enum):
    IDLE = auto()
    DRIVE = auto()
    TURN = auto()


class TurtleSquare(Node):
    """Use turtlesim pose feedback to trace a square without timing delays."""

    POSITION_TOLERANCE = 0.03
    HEADING_TOLERANCE = 0.03
    MAX_LINEAR_SPEED = 2.0
    MAX_ANGULAR_SPEED = 2.5

    def __init__(self) -> None:
        super().__init__('turtle_square')
        self._pose: Pose | None = None
        self._origin: tuple[float, float] | None = None
        self._side_length: float | None = None
        self._corner_index = 0
        self._state = MotionState.IDLE

        self._velocity_publisher = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        self.create_subscription(Pose, '/turtle1/pose', self._pose_callback, 10)
        self.create_subscription(
            Float32, '/square_side_length', self._side_length_callback, 10
        )
        self.create_timer(0.05, self._control_loop)
        self.get_logger().info('Waiting for /turtle1/pose and a positive side length.')

    def _pose_callback(self, message: Pose) -> None:
        self._pose = message

    def _side_length_callback(self, message: Float32) -> None:
        side_length = float(message.data)
        if not math.isfinite(side_length) or side_length <= 0.0:
            self.get_logger().warn('Ignoring non-positive or non-finite side length.')
            return
        if self._pose is None:
            self.get_logger().warn('Pose unavailable; side length will be ignored.')
            return

        self._side_length = side_length
        self._origin = (self._pose.x, self._pose.y)
        self._corner_index = 0
        self._state = MotionState.DRIVE
        self.get_logger().info(
            f'Starting a {side_length:.2f} m square from the current pose.'
        )

    def _target_corner(self) -> tuple[float, float]:
        assert self._origin is not None
        assert self._side_length is not None
        return corner_from_origin(
            self._origin[0], self._origin[1], self._side_length, self._corner_index
        )

    def _control_loop(self) -> None:
        if self._pose is None or self._state is MotionState.IDLE:
            self._publish_stop()
            return

        target_x, target_y = self._target_corner()
        delta_x = target_x - self._pose.x
        delta_y = target_y - self._pose.y
        distance = math.hypot(delta_x, delta_y)

        if self._state is MotionState.DRIVE:
            self._drive_toward_target(distance, delta_x, delta_y)
        else:
            self._turn_toward_target(delta_x, delta_y)

    def _drive_toward_target(
        self, distance: float, delta_x: float, delta_y: float
    ) -> None:
        if distance <= self.POSITION_TOLERANCE:
            self._publish_stop()
            self._advance_side()
            return

        desired_heading = math.atan2(delta_y, delta_x)
        heading_error = angle_error(desired_heading, self._pose.theta)
        command = Twist()
        command.angular.z = self._clamp(4.0 * heading_error, self.MAX_ANGULAR_SPEED)
        if abs(heading_error) <= 0.15:
            command.linear.x = min(self.MAX_LINEAR_SPEED, 1.5 * distance)
        self._velocity_publisher.publish(command)

    def _turn_toward_target(self, delta_x: float, delta_y: float) -> None:
        desired_heading = math.atan2(delta_y, delta_x)
        heading_error = angle_error(desired_heading, self._pose.theta)
        if abs(heading_error) <= self.HEADING_TOLERANCE:
            self._publish_stop()
            self._state = MotionState.DRIVE
            return

        command = Twist()
        command.angular.z = self._clamp(4.0 * heading_error, self.MAX_ANGULAR_SPEED)
        self._velocity_publisher.publish(command)

    def _advance_side(self) -> None:
        self._corner_index += 1
        if self._corner_index == 4:
            self._state = MotionState.IDLE
            self.get_logger().info('Square complete. Waiting for the next side length.')
            return
        self._state = MotionState.TURN

    def _publish_stop(self) -> None:
        self._velocity_publisher.publish(Twist())

    @staticmethod
    def _clamp(value: float, limit: float) -> float:
        return max(-limit, min(limit, value))

    def destroy_node(self) -> bool:
        self._publish_stop()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TurtleSquare()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
