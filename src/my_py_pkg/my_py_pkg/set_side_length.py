#!/usr/bin/env python3
"""Publish user-entered square side lengths without blocking ROS callbacks."""

from queue import Empty, Queue
from threading import Thread

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

from my_py_pkg.square_control import parse_side_length


class SetSideLength(Node):
    """Read side lengths in a terminal and publish them on a ROS 2 topic."""

    def __init__(self) -> None:
        super().__init__('set_side_length')
        self._publisher = self.create_publisher(Float32, '/square_side_length', 10)
        self._pending_lengths: Queue[float] = Queue()
        self.create_timer(0.05, self._publish_pending_lengths)
        self._reader_thread = Thread(target=self._read_input, daemon=True)
        self._reader_thread.start()
        self.get_logger().info('Enter a positive side length, for example: 3.0')

    def _read_input(self) -> None:
        while rclpy.ok():
            try:
                text = input('Square side length (m): ')
            except EOFError:
                self.get_logger().info(
                    'Standard input closed; no more values will be read.'
                )
                return

            side_length = parse_side_length(text)
            if side_length is None:
                self.get_logger().warn(
                    'Enter one finite floating-point value greater than zero.'
                )
                continue
            self._pending_lengths.put(side_length)

    def _publish_pending_lengths(self) -> None:
        while True:
            try:
                side_length = self._pending_lengths.get_nowait()
            except Empty:
                return
            message = Float32()
            message.data = side_length
            self._publisher.publish(message)
            self.get_logger().info(f'Published side length: {side_length:.2f} m')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SetSideLength()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
