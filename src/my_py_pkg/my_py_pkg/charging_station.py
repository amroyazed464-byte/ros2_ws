"""Provide the simulated factory charging station service."""

import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


class ChargingStation(Node):
    """Simulate a fixed-duration fast recharge."""

    def __init__(self):
        super().__init__('charging_station')
        self._service = self.create_service(Trigger, '/recharge', self._recharge_callback)
        self.get_logger().info('充电站已就绪，等待 Burger 到站')

    def _recharge_callback(
        self,
        request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        del request
        self.get_logger().info('正在快充...')
        time.sleep(3.0)
        response.success = True
        response.message = '充电完成，电量已恢复'
        self.get_logger().info(response.message)
        return response


def main(args=None) -> None:
    """Run the charging station node."""
    rclpy.init(args=args)
    node = ChargingStation()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
