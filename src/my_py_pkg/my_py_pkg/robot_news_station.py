#!/user/bin/env python3
from example_interfaces.msg import String
import rclpy
from rclpy.node import Node


class RobotNeswStationNode(Node):
    def __init__(self):
        super().__init__('robot_news_station')
        self.publishers_ = self.create_publisher(String, 'robot_news', 10)
        self.timer_ = self.create_timer(0.5, self.publish_news)
        self.get_logger().info('Robot News Station has beem started.')

    def publish_news(self):
        msg = String()
        msg.data = 'Hello'
        self.publishers_.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotNeswStationNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
