#!/user/bin/env python3
from example_interfaces.msg import String
import rclpy
from rclpy.node import Node


class SmartphoneNode(Node):
    def __init__(self):
        super().__init__('smartphone')
        self.subscriber_ = self.create_subscription(
            String, 'robot_news', self.callback_robot_news, 10)
        self.get_logger().info('Smartphone')

    def callback_robot_news(self, msg: String):
        self.get_logger().info(msg.data)


def main(args=None):
    rclpy.init(args=args)
    node = SmartphoneNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
