"""PyQt5 turtlesim controller and ROS2 publisher."""

from geometry_msgs.msg import Twist
from my_py_pkg.turtle_gui_logic import velocity_for
from rclpy.node import Node


class TurtleGuiNode(Node):
    """Publish GUI movement requests for turtle1."""

    def __init__(self) -> None:
        super().__init__('turtle_gui_controller')
        self._publisher = self.create_publisher(
            Twist,
            '/turtle1/cmd_vel',
            10,
        )

    def publish_action(self, action: str) -> tuple[float, float]:
        """Publish one movement action and return its displayed velocity."""
        linear_x, angular_z = velocity_for(action)
        message = Twist()
        message.linear.x = linear_x
        message.angular.z = angular_z
        self._publisher.publish(message)
        return linear_x, angular_z

    def has_turtlesim(self) -> bool:
        """Return whether cmd_vel currently has a subscriber."""
        return self.count_subscribers('/turtle1/cmd_vel') > 0
