"""Publish an automatically charging and discharging battery level."""

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int32

from my_py_pkg.battery_logic import next_battery_state


class Battery(Node):
    """Simulate a battery that repeatedly discharges and charges."""

    def __init__(self):
        super().__init__('battery')
        self.declare_parameter('initial_level', 100)
        self.declare_parameter('update_period', 1.0)
        self.declare_parameter('step', 10)

        self._level = self.get_parameter('initial_level').value
        update_period = self.get_parameter('update_period').value
        self._step = self.get_parameter('step').value
        if not isinstance(self._level, int) or not 0 <= self._level <= 100:
            raise ValueError('initial_level must be an integer from 0 to 100')
        if not isinstance(update_period, float) or update_period <= 0.0:
            raise ValueError('update_period must be a double greater than 0.0')
        if not isinstance(self._step, int) or not 1 <= self._step <= 100:
            raise ValueError('step must be an integer from 1 to 100')

        self._charging = self._level == 0
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self._publisher = self.create_publisher(Int32, '/battery_level', qos)
        self._publish_level()
        self._timer = self.create_timer(update_period, self._tick)

    def _tick(self) -> None:
        """Advance and publish one charge-cycle step."""
        self._level, self._charging = next_battery_state(
            self._level, self._charging, self._step
        )
        self._publish_level()

    def _publish_level(self) -> None:
        """Publish the current level and its charge phase."""
        message = Int32()
        message.data = self._level
        self._publisher.publish(message)
        phase = 'Charging' if self._charging else 'Discharging'
        self.get_logger().info(f'{phase}: {self._level}%')


def main(args=None) -> None:
    """Run the automatic battery simulator."""
    rclpy.init(args=args)
    node = Battery()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
