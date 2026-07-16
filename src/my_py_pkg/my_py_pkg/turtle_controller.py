"""Teleport turtle1 in response to LED 3 state transitions."""

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import UInt8MultiArray
from turtlesim.srv import TeleportAbsolute

from my_py_pkg.battery_logic import target_for_led3


class TurtleController(Node):
    """Move turtle1 between the charging corner and pool center."""

    def __init__(self):
        super().__init__('turtle_controller')
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._client = self.create_client(
            TeleportAbsolute, '/turtle1/teleport_absolute'
        )
        self._subscription = self.create_subscription(
            UInt8MultiArray, '/led_panel', self._led_callback, qos
        )
        self._requested_led3 = None
        self._completed_led3 = None
        self._in_flight_led3 = None
        self._request_in_flight = False
        self._service_timer = self.create_timer(0.25, self._try_teleport)

    def _led_callback(self, message: UInt8MultiArray) -> None:
        """Store the latest valid LED 3 state and request its target."""
        if len(message.data) < 4:
            self.get_logger().warning(
                'Ignoring LED panel message shorter than 4 entries'
            )
            return

        led3_value = message.data[3]
        try:
            target_for_led3(led3_value)
        except ValueError as error:
            self.get_logger().warning(f'Ignoring LED panel message: {error}')
            return

        if led3_value == self._requested_led3:
            return
        self._requested_led3 = led3_value
        self._try_teleport()

    def _try_teleport(self) -> None:
        """Send the latest desired target when the service is available."""
        if self._request_in_flight or self._requested_led3 is None:
            return
        if self._requested_led3 == self._completed_led3:
            return
        if not self._client.service_is_ready():
            return

        x, y, theta = target_for_led3(self._requested_led3)
        request = TeleportAbsolute.Request()
        request.x = x
        request.y = y
        request.theta = theta
        self._in_flight_led3 = self._requested_led3
        self._request_in_flight = True
        self.get_logger().info(f'Requesting teleport to ({x:.1f}, {y:.1f})')
        future = self._client.call_async(request)
        future.add_done_callback(self._teleport_done)

    def _teleport_done(self, future) -> None:
        """Record a completed request, then honor any newer LED state."""
        completed_led3 = self._in_flight_led3
        self._request_in_flight = False
        self._in_flight_led3 = None
        try:
            future.result()
        except Exception as error:
            self.get_logger().error(f'Teleport failed: {error}')
        else:
            self._completed_led3 = completed_led3
            x, y, _ = target_for_led3(completed_led3)
            self.get_logger().info(
                f'Teleport completed at ({x:.1f}, {y:.1f})'
            )
        self._try_teleport()


def main(args=None) -> None:
    """Run the LED-driven turtlesim service client."""
    rclpy.init(args=args)
    node = TurtleController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
