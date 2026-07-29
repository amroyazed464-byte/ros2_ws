import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool

import serial
import time


class LedBridge(Node):

    def __init__(self):

        super().__init__('led_bridge')


        # STM32串口
        self.serial = serial.Serial(
            '/dev/ttyACM0',
            9600,
            timeout=1
        )


        time.sleep(2)


        # 订阅个人话题
        self.subscription = self.create_subscription(
            Bool,
            'Sunyijie_led_trigger',
            self.callback,
            10
        )


        self.get_logger().info(
            "LED bridge started"
        )


    def callback(self, msg):

        if msg.data:

            self.serial.write(b'1')

            self.get_logger().info(
                "send 1 : LED ON"
            )


        else:

            self.serial.write(b'0')

            self.get_logger().info(
                "send 0 : LED OFF"
            )



def main():

    rclpy.init()


    node = LedBridge()


    rclpy.spin(node)


    node.destroy_node()

    rclpy.shutdown()



if __name__ == '__main__':

    main()