# Turtlesim PyQt5 GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished PyQt5 control panel to `my_py_pkg` that publishes `Twist` commands to `/turtle1/cmd_vel` and launches together with Turtlesim.

**Architecture:** Keep ROS2 and Qt in one process: `QApplication` owns the event loop and a `QTimer` calls non-blocking `rclpy.spin_once()`. A pure command-mapping module is independent of ROS2 and Qt, while the ROS node and GUI window are separate classes joined in `main()`.

**Tech Stack:** Ubuntu 24.04, ROS 2 Jazzy, Python 3, `rclpy`, `geometry_msgs`, `turtlesim`, PyQt5, `ament_python`, `pytest`.

## Global Constraints

- Add the feature to the existing package `src/my_py_pkg`; do not create a new ROS2 package.
- Preserve and separately commit the existing `led_bridge.py`, `config/burger_fast.yaml`, and `setup.py` changes.
- Never commit generated `build/`, `install/`, or `log/` content.
- Node name is `turtle_gui_controller`; executable is `turtle_gui`.
- Publish `geometry_msgs/msg/Twist` to `/turtle1/cmd_vel` with queue depth 10.
- Forward/backward linear speed is `±2.0`; left/right angular speed is `±2.0`; stop is all zero.
- Closing the GUI must publish stop before destroying the node and shutting down ROS2.
- Finish on `main`, merge `feature/turtlesim-pyqt5-gui`, and push `main` to GitHub `origin`.

---

### Task 1: Preserve Existing VM Work and Prepare the Feature Branch

**Files:**
- Existing VM changes: `config/burger_fast.yaml`
- Existing VM changes: `src/my_py_pkg/my_py_pkg/led_bridge.py`
- Existing VM changes: `src/my_py_pkg/setup.py`
- Existing local commits: design and plan documents under `docs/superpowers/`

**Interfaces:**
- Consumes: VM `main` at `625912c`; local `main` containing later work.
- Produces: synchronized `main` and branch `feature/turtlesim-pyqt5-gui`.

- [ ] **Step 1: Stage only the existing source/config changes on the VM**

```bash
cd ~/ros2_ws
git add config/burger_fast.yaml \
  src/my_py_pkg/my_py_pkg/led_bridge.py \
  src/my_py_pkg/setup.py
git diff --cached --check
git status --short
```

Expected: only the three named paths are staged; generated directories remain unstaged.

- [ ] **Step 2: Commit and push the preserved changes**

```bash
git commit -m "feat: add LED serial bridge and Nav2 tuning"
git push origin main
```

Expected: `origin/main` contains the preserved VM work.

- [ ] **Step 3: Merge the remote VM commit into local `main`**

```bash
git fetch origin
git switch main
git merge --no-edit origin/main
git push origin main
```

Expected: local and remote `main` contain both the preserved VM work and the approved design.

- [ ] **Step 4: Create the isolated feature branch**

On Windows:

```bash
git switch -c feature/turtlesim-pyqt5-gui
git push -u origin feature/turtlesim-pyqt5-gui
```

On the VM:

```bash
git fetch origin
git switch --track origin/feature/turtlesim-pyqt5-gui
```

Expected: implementation starts from the synchronized history.

### Task 2: Implement Command Mapping with TDD

**Files:**
- Create: `src/my_py_pkg/test/test_turtle_gui_logic.py`
- Create: `src/my_py_pkg/my_py_pkg/turtle_gui_logic.py`

**Interfaces:**
- Consumes: action names `forward`, `backward`, `left`, `right`, `stop`.
- Produces: `velocity_for(action: str) -> tuple[float, float]`.

- [ ] **Step 1: Write the failing command-mapping tests**

```python
"""Tests for turtlesim GUI command mapping."""

import pytest

from my_py_pkg.turtle_gui_logic import velocity_for


@pytest.mark.parametrize(
    ('action', 'expected'),
    [
        ('forward', (2.0, 0.0)),
        ('backward', (-2.0, 0.0)),
        ('left', (0.0, 2.0)),
        ('right', (0.0, -2.0)),
        ('stop', (0.0, 0.0)),
    ],
)
def test_velocity_for_known_action(action, expected):
    """Each control action maps to the required linear and angular speed."""
    assert velocity_for(action) == expected


def test_velocity_for_rejects_unknown_action():
    """Unknown actions cannot silently move the turtle."""
    with pytest.raises(ValueError, match='Unknown turtle action'):
        velocity_for('jump')
```

- [ ] **Step 2: Transfer the test commit and verify RED**

On Windows:

```bash
git add src/my_py_pkg/test/test_turtle_gui_logic.py
git commit -m "test: specify turtle GUI movement commands"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd ~/ros2_ws/src/my_py_pkg
python3 -m pytest test/test_turtle_gui_logic.py -v
```

Expected: collection fails with `ModuleNotFoundError: my_py_pkg.turtle_gui_logic`.

- [ ] **Step 3: Implement the minimal mapping**

```python
"""Pure velocity mapping for the turtlesim GUI."""

VELOCITIES = {
    'forward': (2.0, 0.0),
    'backward': (-2.0, 0.0),
    'left': (0.0, 2.0),
    'right': (0.0, -2.0),
    'stop': (0.0, 0.0),
}


def velocity_for(action: str) -> tuple[float, float]:
    """Return linear x and angular z velocities for an action."""
    try:
        return VELOCITIES[action]
    except KeyError as error:
        raise ValueError(f'Unknown turtle action: {action}') from error
```

- [ ] **Step 4: Run the tests and verify GREEN**

```bash
python3 -m pytest test/test_turtle_gui_logic.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit, transfer, and verify the tested logic**

On Windows:

```bash
git add src/my_py_pkg/my_py_pkg/turtle_gui_logic.py
git commit -m "feat: map turtle GUI movement commands"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
python3 -m pytest test/test_turtle_gui_logic.py -v
```

Expected: 6 tests pass.

### Task 3: Implement the ROS2 Publisher with TDD

**Files:**
- Create: `src/my_py_pkg/test/test_turtle_gui_node.py`
- Create: `src/my_py_pkg/my_py_pkg/turtle_gui.py`

**Interfaces:**
- Consumes: `velocity_for(action)` from Task 2.
- Produces: class `TurtleGuiNode(Node)` with `publish_action(action: str) -> tuple[float, float]` and `has_turtlesim() -> bool`.

- [ ] **Step 1: Write a failing ROS publisher integration test**

```python
"""ROS integration tests for the turtlesim GUI node."""

import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node

from my_py_pkg.turtle_gui import TurtleGuiNode


def test_node_publishes_forward_twist_and_detects_subscriber():
    """The controller publishes the required Twist on the required topic."""
    rclpy.init()
    controller = TurtleGuiNode()
    listener = Node('turtle_gui_test_listener')
    received = []
    listener.create_subscription(
        Twist, '/turtle1/cmd_vel', received.append, 10
    )
    executor = SingleThreadedExecutor()
    executor.add_node(controller)
    executor.add_node(listener)
    try:
        deadline = time.monotonic() + 3.0
        while not controller.has_turtlesim() and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        assert controller.has_turtlesim()

        assert controller.publish_action('forward') == (2.0, 0.0)
        deadline = time.monotonic() + 3.0
        while not received and time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        assert received
        assert received[-1].linear.x == 2.0
        assert received[-1].angular.z == 0.0
    finally:
        executor.remove_node(listener)
        executor.remove_node(controller)
        listener.destroy_node()
        controller.destroy_node()
        rclpy.shutdown()
```

- [ ] **Step 2: Transfer the node test commit and verify RED**

On Windows:

```bash
git add src/my_py_pkg/test/test_turtle_gui_node.py
git commit -m "test: specify turtlesim GUI ROS publisher"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd ~/ros2_ws/src/my_py_pkg
python3 -m pytest test/test_turtle_gui_node.py -v
```

Expected: import fails because `my_py_pkg.turtle_gui` does not exist.

- [ ] **Step 3: Add the minimal ROS node**

```python
"""PyQt5 turtlesim controller and ROS2 publisher."""

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node

from my_py_pkg.turtle_gui_logic import velocity_for


class TurtleGuiNode(Node):
    """Publish GUI movement requests for turtle1."""

    def __init__(self) -> None:
        super().__init__('turtle_gui_controller')
        self._publisher = self.create_publisher(
            Twist, '/turtle1/cmd_vel', 10
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
```

- [ ] **Step 4: Run logic and node tests and verify GREEN**

```bash
python3 -m pytest \
  test/test_turtle_gui_logic.py \
  test/test_turtle_gui_node.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit, transfer, and verify the ROS publisher**

On Windows:

```bash
git add src/my_py_pkg/my_py_pkg/turtle_gui.py
git commit -m "feat: publish turtlesim GUI velocity commands"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
python3 -m pytest \
  test/test_turtle_gui_logic.py \
  test/test_turtle_gui_node.py -v
```

Expected: all tests pass.

### Task 4: Build the PyQt5 Window with TDD

**Files:**
- Create: `src/my_py_pkg/test/test_turtle_gui_window.py`
- Modify: `src/my_py_pkg/my_py_pkg/turtle_gui.py`

**Interfaces:**
- Consumes: controller methods `publish_action()` and `has_turtlesim()`.
- Produces: `TurtleControlWindow(QMainWindow)`, object names for five buttons, live speed labels, connection status, keyboard controls, and `main(args=None)`.

- [ ] **Step 1: Write failing offscreen GUI interaction tests**

```python
"""Offscreen interaction tests for the PyQt5 turtle controller."""

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton
import pytest

from my_py_pkg.turtle_gui import TurtleControlWindow


class FakeController:
    """Record GUI actions without requiring ROS discovery."""

    def __init__(self):
        self.actions = []
        self.connected = False

    def publish_action(self, action):
        self.actions.append(action)
        from my_py_pkg.turtle_gui_logic import velocity_for
        return velocity_for(action)

    def has_turtlesim(self):
        return self.connected


@pytest.fixture(scope='module')
def app():
    """Provide the single QApplication allowed by Qt."""
    return QApplication.instance() or QApplication([])


def test_buttons_and_keyboard_publish_actions(app):
    """All required mouse and keyboard controls reach the controller."""
    controller = FakeController()
    window = TurtleControlWindow(controller)
    forward = window.findChild(QPushButton, 'forward_button')
    QTest.mouseClick(forward, Qt.LeftButton)
    QTest.keyClick(window, Qt.Key_Left)
    QTest.keyClick(window, Qt.Key_Space)
    assert controller.actions == ['forward', 'left', 'stop']
    assert window.linear_value.text() == '0.0 m/s'
    assert window.angular_value.text() == '0.0 rad/s'
    window.close()
    assert controller.actions == ['forward', 'left', 'stop', 'stop']


def test_connection_status_changes_color_and_text(app):
    """The status distinguishes a missing subscriber from a connected one."""
    controller = FakeController()
    window = TurtleControlWindow(controller)
    window.refresh_connection_status()
    assert window.connection_status.text() == '等待 Turtlesim'
    controller.connected = True
    window.refresh_connection_status()
    assert window.connection_status.text() == '已连接'
    window.close()
```

- [ ] **Step 2: Transfer the GUI test commit and verify RED**

On Windows:

```bash
git add src/my_py_pkg/test/test_turtle_gui_window.py
git commit -m "test: specify PyQt5 turtle controls"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  test/test_turtle_gui_window.py -v
```

Expected: import fails because `TurtleControlWindow` is not defined.

- [ ] **Step 3: Implement the polished window and keyboard behavior**

Add these imports and `TurtleControlWindow` to `turtle_gui.py`:

```python
import sys

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


class TurtleControlWindow(QMainWindow):
    """Dark themed control panel for turtle1."""

    KEY_ACTIONS = {
        Qt.Key_Up: 'forward',
        Qt.Key_Down: 'backward',
        Qt.Key_Left: 'left',
        Qt.Key_Right: 'right',
        Qt.Key_Space: 'stop',
    }

    def __init__(self, controller) -> None:
        super().__init__()
        self._controller = controller
        self._closing = False
        self.setWindowTitle('ROS2 海龟遥控台')
        self.setFixedSize(560, 620)
        self._build_ui()
        self._apply_style()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self.refresh_connection_status)
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
            speed_layout, '线速度', '0.0 m/s'
        )
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setObjectName('separator')
        speed_layout.addWidget(separator)
        self.angular_value = self._speed_column(
            speed_layout, '角速度', '0.0 rad/s'
        )
        root.addWidget(speed_card)

        shortcuts = QLabel('方向键控制移动    SPACE 立即停止')
        shortcuts.setObjectName('shortcuts')
        shortcuts.setAlignment(Qt.AlignCenter)
        root.addWidget(shortcuts)
        self.setCentralWidget(central)

    def _make_button(
        self, symbol: str, text: str, action: str
    ) -> QPushButton:
        button = QPushButton(f'{symbol}\n{text}')
        button.setObjectName(f'{action}_button')
        button.setProperty(
            'controlRole', 'stop' if action == 'stop' else 'direction'
        )
        button.setMinimumSize(132, 92)
        button.clicked.connect(
            lambda checked=False, selected=action:
            self._send_action(selected)
        )
        return button

    @staticmethod
    def _speed_column(
        layout: QHBoxLayout, title: str, initial_value: str
    ) -> QLabel:
        column = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName('metric_title')
        value_label = QLabel(initial_value)
        value_label.setObjectName('metric_value')
        value_label.setAlignment(Qt.AlignCenter)
        column.addWidget(title_label, alignment=Qt.AlignCenter)
        column.addWidget(value_label)
        layout.addLayout(column, 1)
        return value_label

    def _send_action(self, action: str) -> None:
        linear_x, angular_z = self._controller.publish_action(action)
        self.linear_value.setText(f'{linear_x:.1f} m/s')
        self.angular_value.setText(f'{angular_z:.1f} rad/s')

    def keyPressEvent(self, event) -> None:
        action = self.KEY_ACTIONS.get(event.key())
        if action is None:
            super().keyPressEvent(event)
            return
        self._send_action(action)
        event.accept()

    def refresh_connection_status(self) -> None:
        connected = self._controller.has_turtlesim()
        self.connection_status.setText(
            '已连接' if connected else '等待 Turtlesim'
        )
        self.connection_status.setProperty(
            'connectionState', 'online' if connected else 'waiting'
        )
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

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
```

- [ ] **Step 4: Add safe shutdown and the Qt/ROS main loop**

```python
def closeEvent(self, event) -> None:
    """Stop turtle1 exactly once before the window closes."""
    if not self._closing:
        self._closing = True
        self._status_timer.stop()
        self._send_action('stop')
    event.accept()


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
        if not window._closing:
            node.publish_action('stop')
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
```

- [ ] **Step 5: Run all feature tests and verify GREEN**

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  test/test_turtle_gui_logic.py \
  test/test_turtle_gui_node.py \
  test/test_turtle_gui_window.py -v
```

Expected: all tests pass with no Qt traceback.

- [ ] **Step 6: Commit, transfer, and verify the tested GUI**

On Windows:

```bash
git add src/my_py_pkg/my_py_pkg/turtle_gui.py
git commit -m "feat: add PyQt5 turtlesim control panel"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  test/test_turtle_gui_logic.py \
  test/test_turtle_gui_node.py \
  test/test_turtle_gui_window.py -v
```

Expected: all tests pass.

### Task 5: Register the Executable and Launch File with TDD

**Files:**
- Create: `src/my_py_pkg/test/test_turtle_gui_registration.py`
- Create: `src/my_py_pkg/launch/turtle_gui.launch.py`
- Modify: `src/my_py_pkg/setup.py`
- Modify: `src/my_py_pkg/package.xml`

**Interfaces:**
- Consumes: `my_py_pkg.turtle_gui:main`.
- Produces: `ros2 run my_py_pkg turtle_gui` and `ros2 launch my_py_pkg turtle_gui.launch.py`.

- [ ] **Step 1: Write failing registration contract tests**

```python
"""Package registration tests for the turtlesim GUI."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_setup_registers_gui_and_installs_launch_files():
    """The GUI is runnable and its launch file is installed."""
    setup_text = (PACKAGE_ROOT / 'setup.py').read_text(encoding='utf-8')
    assert "'turtle_gui = my_py_pkg.turtle_gui:main'" in setup_text
    assert "glob('launch/*.launch.py')" in setup_text


def test_manifest_declares_gui_runtime_dependencies():
    """ROS and Qt runtime dependencies are declared."""
    package_text = (
        PACKAGE_ROOT / 'package.xml'
    ).read_text(encoding='utf-8')
    assert '<depend>geometry_msgs</depend>' in package_text
    assert '<depend>turtlesim</depend>' in package_text
    assert '<exec_depend>python3-pyqt5</exec_depend>' in package_text
    assert '<exec_depend>launch</exec_depend>' in package_text
    assert '<exec_depend>launch_ros</exec_depend>' in package_text


def test_launch_starts_turtlesim_and_gui():
    """One launch command starts both visible applications."""
    launch_text = (
        PACKAGE_ROOT / 'launch' / 'turtle_gui.launch.py'
    ).read_text(encoding='utf-8')
    assert "package='turtlesim'" in launch_text
    assert "executable='turtlesim_node'" in launch_text
    assert "package='my_py_pkg'" in launch_text
    assert "executable='turtle_gui'" in launch_text
```

- [ ] **Step 2: Transfer the registration test and verify RED**

On Windows:

```bash
git add src/my_py_pkg/test/test_turtle_gui_registration.py
git commit -m "test: specify turtlesim GUI package registration"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
python3 -m pytest test/test_turtle_gui_registration.py -v
```

Expected: all three tests fail because the entry, dependency, and launch file are absent.

- [ ] **Step 3: Register the console entry and Launch installation**

At the top of `setup.py` add:

```python
from glob import glob
import os
```

In `data_files` add:

```python
(os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
```

In `console_scripts` add:

```python
'turtle_gui = my_py_pkg.turtle_gui:main',
```

In `package.xml` add:

```xml
<exec_depend>python3-pyqt5</exec_depend>
<exec_depend>launch</exec_depend>
<exec_depend>launch_ros</exec_depend>
```

- [ ] **Step 4: Create the combined Launch file**

```python
"""Launch turtlesim and the PyQt5 control panel together."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Return the two-node GUI demonstration."""
    return LaunchDescription([
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            name='turtlesim',
            output='screen',
        ),
        Node(
            package='my_py_pkg',
            executable='turtle_gui',
            name='turtle_gui_controller',
            output='screen',
        ),
    ])
```

- [ ] **Step 5: Run registration and feature tests and verify GREEN**

```bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  test/test_turtle_gui_logic.py \
  test/test_turtle_gui_node.py \
  test/test_turtle_gui_window.py \
  test/test_turtle_gui_registration.py -v
```

Expected: all feature tests pass.

- [ ] **Step 6: Commit, transfer, and verify package integration**

On Windows:

```bash
git add src/my_py_pkg/setup.py \
  src/my_py_pkg/package.xml \
  src/my_py_pkg/launch/turtle_gui.launch.py
git commit -m "feat: register turtlesim GUI launch"
git push
```

On the VM:

```bash
cd ~/ros2_ws
git pull --ff-only
cd src/my_py_pkg
python3 -m pytest test/test_turtle_gui_registration.py -v
```

Expected: all registration tests pass.

### Task 6: Add Runbook and Perform Ubuntu Verification

**Files:**
- Create: `docs/turtlesim-pyqt5-gui-runbook.md`

**Interfaces:**
- Consumes: installed `my_py_pkg` GUI and Launch entry.
- Produces: copyable build, run, verification, troubleshooting, and video steps.

- [ ] **Step 1: Write the runbook**

Document these exact commands:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
ros2 launch my_py_pkg turtle_gui.launch.py
```

Also document:

- Required packages: `ros-jazzy-turtlesim`, `python3-pyqt5`.
- Manual verification with `ros2 topic echo /turtle1/cmd_vel`.
- Button and keyboard acceptance sequence.
- Side-by-side window placement and the 20–40 second video sequence.
- Troubleshooting for an orange waiting status and missing display.

- [ ] **Step 2: Run source tests, package build, and package tests**

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  src/my_py_pkg/test/test_turtle_gui_logic.py \
  src/my_py_pkg/test/test_turtle_gui_node.py \
  src/my_py_pkg/test/test_turtle_gui_window.py \
  src/my_py_pkg/test/test_turtle_gui_registration.py -v
colcon build --packages-select my_py_pkg --symlink-install
colcon test --packages-select my_py_pkg --event-handlers console_direct+
colcon test-result --verbose
```

Expected: feature tests pass, build exits 0, and test result reports no failures.

- [ ] **Step 3: Run the real desktop demonstration**

From an Ubuntu desktop terminal:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch my_py_pkg turtle_gui.launch.py
```

Verify:

- Both windows are visible.
- Connection changes from orange to green.
- Five buttons move/stop turtle1 correctly.
- Arrow keys and Space match the buttons.
- Closing the GUI stops turtle1.

- [ ] **Step 4: Inspect the final branch diff**

```bash
git status --short
git diff main...HEAD --check
git diff --stat main...HEAD
git log --oneline --decorate main..HEAD
```

Expected: only source, tests, Launch, manifest/setup, and documentation changes are present.

- [ ] **Step 5: Commit the runbook**

```bash
git add docs/turtlesim-pyqt5-gui-runbook.md
git commit -m "docs: add turtlesim GUI demo runbook"
git push origin feature/turtlesim-pyqt5-gui
```

### Task 7: Merge, Reverify, and Push GitHub

**Files:**
- Merge all feature files into `main`.

**Interfaces:**
- Consumes: verified `feature/turtlesim-pyqt5-gui`.
- Produces: GitHub `origin/main` containing the completed homework.

- [ ] **Step 1: Merge the feature branch**

On the VM, after the real desktop verification:

```bash
cd ~/ros2_ws
git switch main
git pull --ff-only
git merge --no-ff feature/turtlesim-pyqt5-gui \
  -m "merge: add PyQt5 turtlesim controller"
```

- [ ] **Step 2: Re-run the final verification on merged `main`**

```bash
source /opt/ros/jazzy/setup.bash
QT_QPA_PLATFORM=offscreen python3 -m pytest \
  src/my_py_pkg/test/test_turtle_gui_logic.py \
  src/my_py_pkg/test/test_turtle_gui_node.py \
  src/my_py_pkg/test/test_turtle_gui_window.py \
  src/my_py_pkg/test/test_turtle_gui_registration.py -v
colcon build --packages-select my_py_pkg --symlink-install
colcon test --packages-select my_py_pkg --event-handlers console_direct+
colcon test-result --verbose
```

Expected: all commands exit 0 and test results show zero failures.

- [ ] **Step 3: Push and confirm the remote main branch**

On the VM:

```bash
git push origin main
git fetch origin
test "$(git rev-parse main)" = "$(git rev-parse origin/main)"
git status --short
```

Expected: local and GitHub `main` point to the same merge commit; only known generated VM changes remain unstaged.

- [ ] **Step 4: Fast-forward the Windows checkout**

On Windows:

```bash
git switch main
git pull --ff-only origin main
git status --short
```

Expected: Windows `main` matches GitHub and has no uncommitted files.
