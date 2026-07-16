# Battery, LED Panel, and Turtle Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and register three ROS 2 Python nodes that simulate a cyclic battery, latch LED 3 while charging, and teleport `turtle1` in sync with that LED.

**Architecture:** Pure functions implement the battery transition, LED latch, and LED-to-target mapping so their behavior is testable without ROS. Thin `rclpy` node classes publish or subscribe using reliable transient-local QoS, and the controller serializes asynchronous `TeleportAbsolute` calls while retaining the latest requested state.

**Tech Stack:** Python 3, ROS 2 Jazzy, `rclpy`, `std_msgs`, `turtlesim`, `pytest`, `ament_python`

## Global Constraints

- Package: `my_py_pkg` under `src/my_py_pkg`.
- Platform target: Ubuntu 24.04 with ROS 2 Jazzy.
- Topic `/battery_level`: `std_msgs/msg/Int32`.
- Topic `/led_panel`: `std_msgs/msg/UInt8MultiArray`; `data[3]` is LED 3.
- Service `/turtle1/teleport_absolute`: `turtlesim/srv/TeleportAbsolute`.
- Safe target: `(11.0, 11.0, 0.0)`; center target: `(5.5, 5.5, 0.0)`.
- Do not edit generated `build/`, `install/`, or `log/` content.
- Do not add third-party dependencies.

---

### Task 1: Pure State Logic

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/battery_logic.py`
- Create: `src/my_py_pkg/test/test_battery_led_logic.py`

**Interfaces:**
- Produces: `next_battery_state(level: int, charging: bool, step: int) -> tuple[int, bool]`
- Produces: `next_led3_state(level: int, led3_on: bool) -> bool`
- Produces: `target_for_led3(value: int) -> tuple[float, float, float]`

- [ ] **Step 1: Write failing pure-logic tests**

```python
"""Unit tests for battery, LED, and turtle target state logic."""

import pytest

from my_py_pkg.battery_logic import (
    next_battery_state,
    next_led3_state,
    target_for_led3,
)


def test_battery_reverses_to_charging_at_empty():
    assert next_battery_state(10, False, 10) == (0, True)


def test_battery_reverses_to_discharging_at_full():
    assert next_battery_state(90, True, 10) == (100, False)


def test_battery_clamps_oversized_steps():
    assert next_battery_state(5, False, 10) == (0, True)
    assert next_battery_state(95, True, 10) == (100, False)


def test_led3_latches_from_empty_until_full():
    assert next_led3_state(0, False) is True
    assert next_led3_state(50, True) is True
    assert next_led3_state(100, True) is False


def test_turtle_target_matches_binary_led_value():
    assert target_for_led3(1) == (11.0, 11.0, 0.0)
    assert target_for_led3(0) == (5.5, 5.5, 0.0)


def test_turtle_target_rejects_non_binary_value():
    with pytest.raises(ValueError, match='LED 3 value must be 0 or 1'):
        target_for_led3(2)
```

- [ ] **Step 2: Run the test and verify the missing module failure**

Run: `python -m pytest test/test_battery_led_logic.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'my_py_pkg.battery_logic'`.

- [ ] **Step 3: Implement the minimal pure logic**

```python
"""Pure state transitions shared by the battery demonstration nodes."""


def next_battery_state(
    level: int, charging: bool, step: int
) -> tuple[int, bool]:
    """Advance one battery tick and reverse direction at a boundary."""
    next_level = level + step if charging else level - step
    next_level = max(0, min(100, next_level))
    if next_level == 0:
        return next_level, True
    if next_level == 100:
        return next_level, False
    return next_level, charging


def next_led3_state(level: int, led3_on: bool) -> bool:
    """Latch LED 3 on at empty and off only after reaching full charge."""
    bounded_level = max(0, min(100, level))
    if bounded_level == 0:
        return True
    if bounded_level == 100:
        return False
    return led3_on


def target_for_led3(value: int) -> tuple[float, float, float]:
    """Return the turtlesim target associated with a binary LED value."""
    if value == 1:
        return 11.0, 11.0, 0.0
    if value == 0:
        return 5.5, 5.5, 0.0
    raise ValueError('LED 3 value must be 0 or 1')
```

- [ ] **Step 4: Run the pure-logic tests and verify green**

Run: `python -m pytest test/test_battery_led_logic.py -q`

Expected: `6 passed`.

- [ ] **Step 5: Commit the state logic**

```bash
git add src/my_py_pkg/my_py_pkg/battery_logic.py src/my_py_pkg/test/test_battery_led_logic.py
git commit -m "feat: add battery LED state logic"
```

### Task 2: Battery and LED ROS Nodes

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/battery.py`
- Create: `src/my_py_pkg/my_py_pkg/led_panel.py`
- Create: `src/my_py_pkg/test/test_battery_led_nodes.py`

**Interfaces:**
- Consumes: `next_battery_state()` and `next_led3_state()` from Task 1.
- Produces: `Battery` and `LedPanel` node classes plus their `main()` functions.

- [ ] **Step 1: Write failing static node-contract tests**

```python
"""Static contract tests that can run without importing ROS on Windows."""

from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / 'my_py_pkg'


def test_battery_uses_required_topic_message_and_parameters():
    source = (PACKAGE / 'battery.py').read_text(encoding='utf-8')
    assert "super().__init__('battery')" in source
    assert "create_publisher(Int32, '/battery_level'" in source
    assert "declare_parameter('initial_level', 100)" in source
    assert "declare_parameter('update_period', 1.0)" in source
    assert "declare_parameter('step', 10)" in source


def test_led_panel_uses_required_topic_and_four_led_payload():
    source = (PACKAGE / 'led_panel.py').read_text(encoding='utf-8')
    assert "super().__init__('led_panel')" in source
    assert "create_subscription(Int32, '/battery_level'" in source
    assert "create_publisher(UInt8MultiArray, '/led_panel'" in source
    assert 'message.data = [0, 0, 0, int(self._led3_on)]' in source
```

- [ ] **Step 2: Run and verify missing-file failures**

Run: `python -m pytest test/test_battery_led_nodes.py -q`

Expected: two failures with `FileNotFoundError` for `battery.py` and `led_panel.py`.

- [ ] **Step 3: Implement `battery.py`**

```python
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
        self._level, self._charging = next_battery_state(
            self._level, self._charging, self._step
        )
        self._publish_level()

    def _publish_level(self) -> None:
        message = Int32()
        message.data = self._level
        self._publisher.publish(message)
        phase = 'Charging' if self._charging else 'Discharging'
        self.get_logger().info(f'{phase}: {self._level}%')


def main(args=None) -> None:
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
```

- [ ] **Step 4: Implement `led_panel.py`**

```python
"""Translate battery boundary states into a four-LED panel message."""

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int32, UInt8MultiArray

from my_py_pkg.battery_logic import next_led3_state


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
        self._publisher = self.create_publisher(
            UInt8MultiArray, '/led_panel', qos
        )
        self._subscription = self.create_subscription(
            Int32, '/battery_level', self._battery_callback, qos
        )

    def _battery_callback(self, message: Int32) -> None:
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
        message = UInt8MultiArray()
        message.data = [0, 0, 0, int(self._led3_on)]
        self._publisher.publish(message)


def main(args=None) -> None:
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
```

- [ ] **Step 5: Run node-contract and pure-logic tests**

Run: `python -m pytest test/test_battery_led_logic.py test/test_battery_led_nodes.py -q`

Expected: `8 passed`.

- [ ] **Step 6: Commit the publisher pipeline**

```bash
git add src/my_py_pkg/my_py_pkg/battery.py src/my_py_pkg/my_py_pkg/led_panel.py src/my_py_pkg/test/test_battery_led_nodes.py
git commit -m "feat: publish battery and LED panel states"
```

### Task 3: Turtle Controller ROS Node

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/turtle_controller.py`
- Create: `src/my_py_pkg/test/test_turtle_controller.py`

**Interfaces:**
- Consumes: `target_for_led3(value: int)` from Task 1.
- Produces: `TurtleController` node and `main()`.

- [ ] **Step 1: Write failing static controller-contract tests**

```python
"""Static ROS contract tests for the turtle controller."""

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'my_py_pkg'
    / 'turtle_controller.py'
)


def test_controller_subscribes_and_calls_required_service():
    source = SOURCE.read_text(encoding='utf-8')
    assert "super().__init__('turtle_controller')" in source
    assert "create_subscription(UInt8MultiArray, '/led_panel'" in source
    assert "create_client(TeleportAbsolute, '/turtle1/teleport_absolute')" in source


def test_controller_validates_payload_and_suppresses_duplicates():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'if len(message.data) < 4:' in source
    assert 'if led3_value == self._requested_led3:' in source
    assert 'target_for_led3(led3_value)' in source


def test_controller_serializes_requests_and_retains_latest_state():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'self._request_in_flight' in source
    assert 'self._requested_led3' in source
    assert 'self._completed_led3' in source
    assert 'future.add_done_callback(self._teleport_done)' in source
```

- [ ] **Step 2: Run and verify the missing-file failures**

Run: `python -m pytest test/test_turtle_controller.py -q`

Expected: three failures with `FileNotFoundError` for `turtle_controller.py`.

- [ ] **Step 3: Implement the asynchronous controller**

```python
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
        if len(message.data) < 4:
            self.get_logger().warning('Ignoring LED panel message shorter than 4')
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
            self.get_logger().info(f'Teleport completed at ({x:.1f}, {y:.1f})')
        self._try_teleport()


def main(args=None) -> None:
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
```

- [ ] **Step 4: Run controller and logic tests**

Run: `python -m pytest test/test_battery_led_logic.py test/test_turtle_controller.py -q`

Expected: `9 passed`.

- [ ] **Step 5: Commit the service client**

```bash
git add src/my_py_pkg/my_py_pkg/turtle_controller.py src/my_py_pkg/test/test_turtle_controller.py
git commit -m "feat: teleport turtle from LED state"
```

### Task 4: Register Executables and Verify the Package

**Files:**
- Modify: `src/my_py_pkg/setup.py`
- Create: `src/my_py_pkg/test/test_battery_demo_registration.py`

**Interfaces:**
- Consumes: the three node `main()` functions from Tasks 2 and 3.
- Produces: `ros2 run my_py_pkg battery`, `led_panel`, and `turtle_controller`.

- [ ] **Step 1: Write the failing registration test**

```python
"""Console script registration tests for the battery demonstration."""

from pathlib import Path


def test_all_battery_demo_nodes_are_registered():
    setup_source = (
        Path(__file__).resolve().parents[1] / 'setup.py'
    ).read_text(encoding='utf-8')
    assert 'battery = my_py_pkg.battery:main' in setup_source
    assert 'led_panel = my_py_pkg.led_panel:main' in setup_source
    assert (
        'turtle_controller = my_py_pkg.turtle_controller:main'
        in setup_source
    )
```

- [ ] **Step 2: Run and verify registration failure**

Run: `python -m pytest test/test_battery_demo_registration.py -q`

Expected: failure because the three `console_scripts` entries are absent.

- [ ] **Step 3: Add all three console scripts**

Add these strings to the existing `console_scripts` list without removing any
existing entry:

```python
"battery = my_py_pkg.battery:main",
"led_panel = my_py_pkg.led_panel:main",
"turtle_controller = my_py_pkg.turtle_controller:main",
```

No `package.xml` change is necessary because `rclpy`, `std_msgs`, and
`turtlesim` are already declared.

- [ ] **Step 4: Run all package tests**

Run: `python -m pytest test -q`

Expected: all tests pass with no failures.

- [ ] **Step 5: Inspect the complete source diff**

Run: `git diff --check && git status --short && git diff --stat`

Expected: no whitespace errors; only the planned source, test, setup, and plan
files are present.

- [ ] **Step 6: Commit registration**

```bash
git add src/my_py_pkg/setup.py src/my_py_pkg/test/test_battery_demo_registration.py
git commit -m "build: register battery turtle demo nodes"
```

### Task 5: Ubuntu ROS 2 Build and Runtime Verification

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes: all registered executables.
- Produces: runtime evidence and an exported MP4 demonstration.

- [ ] **Step 1: Build the package in Ubuntu**

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
```

Expected: `Summary: 1 package finished` with no failed package.

- [ ] **Step 2: Run ROS package tests**

```bash
colcon test --packages-select my_py_pkg
colcon test-result --verbose
```

Expected: zero failed tests.

- [ ] **Step 3: Start the four programs in Terminator panes**

Run one command per pane after sourcing ROS and the workspace:

```bash
ros2 run turtlesim turtlesim_node
ros2 run my_py_pkg led_panel
ros2 run my_py_pkg battery
ros2 run my_py_pkg turtle_controller
```

Expected: battery levels cycle; LED 3 turns on at 0 and off at 100; controller
logs completed teleports; turtlesim moves to the upper-right and then center.

- [ ] **Step 4: Inspect live ROS contracts**

```bash
ros2 topic info /battery_level
ros2 topic info /led_panel
ros2 service type /turtle1/teleport_absolute
```

Expected types: `std_msgs/msg/Int32`, `std_msgs/msg/UInt8MultiArray`, and
`turtlesim/srv/TeleportAbsolute`.

- [ ] **Step 5: Record and export the synchronized demonstration**

Arrange Terminator beside the turtlesim window, start the Ubuntu desktop screen
recorder, capture at least one empty-to-full transition, stop recording, and
export to an MP4 such as `battery_turtle_demo.mp4`. Verify playback shows both
the turtle movement and matching battery/LED/controller log timestamps.
