"""PyQt5 turtlesim controller and ROS2 publisher."""

import sys

from geometry_msgs.msg import Twist
from my_py_pkg.turtle_gui_logic import velocity_for
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import rclpy
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


class TurtleControlWindow(QMainWindow):
    """Dark themed control panel for turtle1."""

    KEY_ACTIONS = {
        Qt.Key_Up: 'forward',
        Qt.Key_Down: 'backward',
        Qt.Key_Left: 'left',
        Qt.Key_Right: 'right',
        Qt.Key_Space: 'stop',
    }

    def __init__(self, controller: TurtleGuiNode) -> None:
        super().__init__()
        self._controller = controller
        self._closing = False
        self.setWindowTitle('ROS2 海龟遥控台')
        self.setFixedSize(560, 620)
        self._build_ui()
        self._apply_style()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(
            self.refresh_connection_status
        )
        self._status_timer.start(500)
        self.refresh_connection_status()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName('central')
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        heading = QLabel('ROS2 海龟遥控台')
        heading.setObjectName('heading')
        subtitle = QLabel('TURTLESIM  /  CMD_VEL')
        subtitle.setObjectName('subtitle')
        self.connection_status = QLabel()
        self.connection_status.setObjectName('connection_status')

        header_text = QVBoxLayout()
        header_text.addWidget(heading)
        header_text.addWidget(subtitle)
        header = QHBoxLayout()
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(self.connection_status)
        root.addLayout(header)

        control_card = QFrame()
        control_card.setObjectName('card')
        controls = QGridLayout(control_card)
        controls.setContentsMargins(24, 24, 24, 24)
        controls.setSpacing(12)
        button_specs = {
            'forward': ('↑', '前进', 0, 1),
            'left': ('↶', '左转', 1, 0),
            'stop': ('■', '停止', 1, 1),
            'right': ('↷', '右转', 1, 2),
            'backward': ('↓', '后退', 2, 1),
        }
        for action, (symbol, text, row, column) in button_specs.items():
            button = self._make_button(symbol, text, action)
            setattr(self, f'{action}_button', button)
            controls.addWidget(button, row, column)
        root.addWidget(control_card)

        speed_card = QFrame()
        speed_card.setObjectName('card')
        speed_layout = QHBoxLayout(speed_card)
        speed_layout.setContentsMargins(24, 18, 24, 18)
        self.linear_value = self._speed_column(
            speed_layout,
            '线速度',
            '0.0 m/s',
        )
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setObjectName('separator')
        speed_layout.addWidget(separator)
        self.angular_value = self._speed_column(
            speed_layout,
            '角速度',
            '0.0 rad/s',
        )
        root.addWidget(speed_card)

        shortcuts = QLabel('方向键控制移动    SPACE 立即停止')
        shortcuts.setObjectName('shortcuts')
        shortcuts.setAlignment(Qt.AlignCenter)
        root.addWidget(shortcuts)
        self.setCentralWidget(central)

    def _make_button(
        self,
        symbol: str,
        text: str,
        action: str,
    ) -> QPushButton:
        button = QPushButton(f'{symbol}\n{text}')
        button.setObjectName(f'{action}_button')
        button.setProperty(
            'controlRole',
            'stop' if action == 'stop' else 'direction',
        )
        button.setMinimumSize(132, 92)
        button.clicked.connect(
            lambda checked=False, selected=action:
            self._send_action(selected)
        )
        return button

    @staticmethod
    def _speed_column(
        layout: QHBoxLayout,
        title: str,
        initial_value: str,
    ) -> QLabel:
        column = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName('metric_title')
        value_label = QLabel(initial_value)
        value_label.setObjectName('metric_value')
        value_label.setAlignment(Qt.AlignCenter)
        column.addWidget(title_label, 0, Qt.AlignCenter)
        column.addWidget(value_label)
        layout.addLayout(column, 1)
        return value_label

    def _send_action(self, action: str) -> None:
        linear_x, angular_z = self._controller.publish_action(action)
        self.linear_value.setText(f'{linear_x:.1f} m/s')
        self.angular_value.setText(f'{angular_z:.1f} rad/s')

    def keyPressEvent(self, event) -> None:
        """Translate the arrow and space keys into movement actions."""
        action = self.KEY_ACTIONS.get(event.key())
        if action is None:
            super().keyPressEvent(event)
            return
        self._send_action(action)
        event.accept()

    def refresh_connection_status(self) -> None:
        """Refresh the Turtlesim subscriber status badge."""
        connected = self._controller.has_turtlesim()
        self.connection_status.setText(
            '已连接' if connected else '等待 Turtlesim'
        )
        self.connection_status.setProperty(
            'connectionState',
            'online' if connected else 'waiting',
        )
        style = self.connection_status.style()
        style.unpolish(self.connection_status)
        style.polish(self.connection_status)

    def closeEvent(self, event) -> None:
        """Stop turtle1 exactly once before the window closes."""
        if not self._closing:
            self._closing = True
            self._status_timer.stop()
            try:
                self._send_action('stop')
            except Exception as error:
                self._controller.get_logger().error(
                    f'Unable to publish stop while closing: {error}'
                )
        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#central {
                background: #0b1120;
                color: #e5edf8;
                font-family: "Noto Sans CJK SC", "Noto Sans", sans-serif;
            }
            QLabel#heading {
                color: #f8fafc;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subtitle, QLabel#shortcuts, QLabel#metric_title {
                color: #8190a8;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QLabel#connection_status {
                border-radius: 14px;
                font-weight: 700;
                padding: 7px 13px;
            }
            QLabel#connection_status[connectionState="online"] {
                background: #123d35;
                color: #67e8b5;
            }
            QLabel#connection_status[connectionState="waiting"] {
                background: #4a3214;
                color: #fbbf5a;
            }
            QFrame#card {
                background: #111a2d;
                border: 1px solid #26334a;
                border-radius: 18px;
            }
            QPushButton {
                border: 1px solid #33445f;
                border-radius: 15px;
                color: #f8fafc;
                font-size: 17px;
                font-weight: 700;
                padding: 8px;
            }
            QPushButton[controlRole="direction"] {
                background: #1d4f91;
            }
            QPushButton[controlRole="direction"]:hover {
                background: #2868b9;
                border-color: #60a5fa;
            }
            QPushButton[controlRole="direction"]:pressed {
                background: #173c6d;
            }
            QPushButton[controlRole="stop"] {
                background: #b42332;
                border-color: #f05a68;
            }
            QPushButton[controlRole="stop"]:hover {
                background: #d02d3f;
            }
            QPushButton[controlRole="stop"]:pressed {
                background: #8f1d2a;
            }
            QLabel#metric_value {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 700;
                padding: 3px;
            }
            QFrame#separator {
                background: #31405a;
                max-width: 1px;
            }
            """
        )


def main(args=None) -> None:
    """Run the ROS2-backed PyQt5 controller."""
    rclpy.init(args=args)
    app = QApplication.instance() or QApplication(sys.argv)
    node = TurtleGuiNode()
    window = TurtleControlWindow(node)
    ros_timer = QTimer()
    ros_timer.timeout.connect(
        lambda: rclpy.spin_once(node, timeout_sec=0.0)
    )
    ros_timer.start(20)
    window.show()

    try:
        app.exec_()
    finally:
        ros_timer.stop()
        try:
            node.publish_action('stop')
        except Exception as error:
            node.get_logger().error(
                f'Unable to publish final stop command: {error}'
            )
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
