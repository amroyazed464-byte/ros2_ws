"""Translate battery boundary states into a four-LED panel message."""

from my_py_pkg.battery_logic import next_led3_state
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int32, UInt8MultiArray


class LedPanel(Node):
    """Latch LED 3 while the simulated battery is charging."""

    def __init__(self):
        super().__init__('led_panel')
        self._led3_on = False
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._publisher = self.create_publisher(UInt8MultiArray, '/led_panel', qos)
        self._subscription = self.create_subscription(
            Int32, '/battery_level', self._battery_callback, qos
        )

    def _battery_callback(self, message: Int32) -> None:
        """Update the LED latch from a received battery level."""
        level = message.data
        bounded_level = max(0, min(100, level))
        if bounded_level != level:
            self.get_logger().warning(
                f'Battery level {level} is out of range; using {bounded_level}'
            )
        previous = self._led3_on
        self._led3_on = next_led3_state(bounded_level, self._led3_on)
        if self._led3_on != previous:
            state = 'ON (battery empty)' if self._led3_on else 'OFF (battery full)'
            self.get_logger().info(f'LED 3 {state}')
        self._publish_panel()

    def _publish_panel(self) -> None:
        """Publish all four LED values in index order."""
        message = UInt8MultiArray()
        message.data = [0, 0, 0, int(self._led3_on)]
        self._publisher.publish(message)


def main(args=None) -> None:
    """Run the battery-to-LED adapter node."""
    rclpy.init(args=args)
    node = LedPanel()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
