# AGV Battery Interruption and Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two ROS 2 Python nodes that run a TurtleBot3 Burger pickup/drop-off loop, interrupt it at low battery, recharge through a service, and resume the interrupted goal.

**Architecture:** `AgvCommander` subclasses Nav2 Simple Commander's `BasicNavigator` and owns a linear polling loop, avoiding timer callbacks and nested executors around `isTaskComplete()`. ROS-independent battery and workflow transitions live in `agv_logic.py`; `ChargingStation` is a separate `Trigger` service node.

**Tech Stack:** Python 3, ROS 2 Jazzy, `rclpy`, `nav2_simple_commander`, `geometry_msgs`, `std_msgs`, `std_srvs`, `pytest`, `ament_python`

## Global Constraints

- Repository target: Ubuntu 24.04 with ROS 2 Jazzy.
- Package: `my_py_pkg` under `src/my_py_pkg`.
- Work only on `agent/agv-battery-resume`; preserve all existing package features.
- Do not modify generated `build/`, `install/`, or `log/` content.
- Battery starts at `100.0`, drains at `0.5%` per second, publishes once per second, and triggers recovery at `<= 20.0%`.
- Work goals are pickup `(2.5, 1.0)` and drop-off `(0.0, 1.0)`; charging is `(0.0, 0.0)`.
- Battery topic: `/burger_battery` using `std_msgs/msg/Float32`.
- Recharge service: `/recharge` using `std_srvs/srv/Trigger`.
- Navigation frame: `map`; close-enough arrival tolerance: `0.25 m`.
- Failed navigation and recharge operations retain their target and retry.
- Windows checks cannot be presented as Ubuntu ROS 2 runtime verification.

---

## File Structure

- Create `src/my_py_pkg/my_py_pkg/agv_logic.py`: pure battery math and work/recovery state.
- Create `src/my_py_pkg/my_py_pkg/charging_station.py`: independent recharge service node.
- Create `src/my_py_pkg/my_py_pkg/agv_commander.py`: Nav2 navigation and recharge orchestration.
- Create `src/my_py_pkg/test/test_agv_logic.py`: pure state tests.
- Create `src/my_py_pkg/test/test_charging_station_contract.py`: ROS-independent service source contract.
- Create `src/my_py_pkg/test/test_agv_commander_contract.py`: ROS-independent commander source contract.
- Create `src/my_py_pkg/test/test_agv_registration.py`: package dependency and executable registration.
- Modify `src/my_py_pkg/setup.py`: register both executables.
- Modify `src/my_py_pkg/package.xml`: declare `nav2_simple_commander`.
- Create `docs/ros2-homework-7-runbook.md`: Ubuntu build, launch, inspection, and simulation checks.

### Task 1: Pure Battery and Workflow State

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/agv_logic.py`
- Create: `src/my_py_pkg/test/test_agv_logic.py`

**Interfaces:**
- Produces: `deplete_battery(level: float, elapsed_seconds: float, rate_per_second: float = 0.5) -> float`
- Produces: `should_interrupt_for_charge(level: float, recovering: bool, threshold: float = 20.0) -> bool`
- Produces: `AgvWorkflow.current_work_target: str`
- Produces: `AgvWorkflow.begin_recovery() -> bool`
- Produces: `AgvWorkflow.complete_recharge() -> str`
- Produces: `AgvWorkflow.complete_work_target() -> str`
- Produces constants: `PICKUP`, `DROPOFF`

- [ ] **Step 1: Write failing pure-logic tests**

```python
"""Unit tests for AGV battery depletion and interrupted-goal memory."""

import pytest

from my_py_pkg.agv_logic import (
    DROPOFF,
    PICKUP,
    AgvWorkflow,
    deplete_battery,
    should_interrupt_for_charge,
)


def test_battery_depletion_uses_elapsed_time_and_clamps_at_zero():
    assert deplete_battery(100.0, 2.0) == 99.0
    assert deplete_battery(0.2, 1.0) == 0.0


def test_battery_depletion_rejects_invalid_inputs():
    with pytest.raises(ValueError, match='elapsed_seconds'):
        deplete_battery(50.0, -1.0)
    with pytest.raises(ValueError, match='rate_per_second'):
        deplete_battery(50.0, 1.0, 0.0)


def test_low_battery_interrupts_only_outside_recovery():
    assert should_interrupt_for_charge(20.0, False) is True
    assert should_interrupt_for_charge(19.5, False) is True
    assert should_interrupt_for_charge(20.0, True) is False
    assert should_interrupt_for_charge(20.1, False) is False


def test_work_targets_alternate_after_completion():
    workflow = AgvWorkflow()
    assert workflow.current_work_target == PICKUP
    assert workflow.complete_work_target() == DROPOFF
    assert workflow.complete_work_target() == PICKUP


def test_recovery_remembers_and_restores_the_interrupted_goal():
    workflow = AgvWorkflow(current_work_target=DROPOFF)
    assert workflow.begin_recovery() is True
    assert workflow.recovering is True
    assert workflow.interrupted_target == DROPOFF
    assert workflow.begin_recovery() is False

    assert workflow.complete_recharge() == DROPOFF
    assert workflow.recovering is False
    assert workflow.interrupted_target is None
    assert workflow.current_work_target == DROPOFF


def test_work_completion_is_rejected_during_recovery():
    workflow = AgvWorkflow()
    workflow.begin_recovery()
    with pytest.raises(RuntimeError, match='during recovery'):
        workflow.complete_work_target()


def test_recharge_completion_requires_an_interrupted_goal():
    with pytest.raises(RuntimeError, match='without an interrupted goal'):
        AgvWorkflow().complete_recharge()
```

- [ ] **Step 2: Run the tests and verify the missing-module failure**

Run from `src/my_py_pkg`:

```bash
python -m pytest test/test_agv_logic.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'my_py_pkg.agv_logic'`.

- [ ] **Step 3: Implement the minimal pure state module**

```python
"""Pure state transitions for the factory AGV demonstration."""

from dataclasses import dataclass


PICKUP = 'pickup'
DROPOFF = 'dropoff'


def deplete_battery(
    level: float,
    elapsed_seconds: float,
    rate_per_second: float = 0.5,
) -> float:
    """Decrease a battery level according to elapsed monotonic time."""
    if elapsed_seconds < 0.0:
        raise ValueError('elapsed_seconds must not be negative')
    if rate_per_second <= 0.0:
        raise ValueError('rate_per_second must be greater than zero')
    return max(0.0, min(100.0, level - elapsed_seconds * rate_per_second))


def should_interrupt_for_charge(
    level: float,
    recovering: bool,
    threshold: float = 20.0,
) -> bool:
    """Return whether low battery should start a new recovery cycle."""
    return not recovering and level <= threshold


@dataclass
class AgvWorkflow:
    """Remember the work target across a charging interruption."""

    current_work_target: str = PICKUP
    interrupted_target: str | None = None
    recovering: bool = False

    def begin_recovery(self) -> bool:
        """Latch recovery and preserve the current work target once."""
        if self.recovering:
            return False
        self.interrupted_target = self.current_work_target
        self.recovering = True
        return True

    def complete_recharge(self) -> str:
        """Restore and return the work target saved before charging."""
        if not self.recovering or self.interrupted_target is None:
            raise RuntimeError('cannot complete recharge without an interrupted goal')
        self.current_work_target = self.interrupted_target
        self.interrupted_target = None
        self.recovering = False
        return self.current_work_target

    def complete_work_target(self) -> str:
        """Advance to the opposite station after a work goal completes."""
        if self.recovering:
            raise RuntimeError('cannot complete a work target during recovery')
        self.current_work_target = (
            DROPOFF if self.current_work_target == PICKUP else PICKUP
        )
        return self.current_work_target
```

- [ ] **Step 4: Run the pure tests and verify green**

Run:

```bash
python -m pytest test/test_agv_logic.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit the pure state behavior**

```bash
git add src/my_py_pkg/my_py_pkg/agv_logic.py src/my_py_pkg/test/test_agv_logic.py
git commit -m "feat: add AGV battery recovery state"
```

### Task 2: Charging Station Service

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/charging_station.py`
- Create: `src/my_py_pkg/test/test_charging_station_contract.py`

**Interfaces:**
- Produces: `ChargingStation(Node)`
- Produces: `/recharge` service using `std_srvs/srv/Trigger`
- Produces: `main(args=None) -> None`

- [ ] **Step 1: Write the failing source-contract test**

```python
"""Static contract checks for the recharge service node."""

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'my_py_pkg'
    / 'charging_station.py'
)


def test_charging_station_exposes_the_required_trigger_service():
    source = SOURCE.read_text(encoding='utf-8')
    assert "super().__init__('charging_station')" in source
    assert "create_service(Trigger, '/recharge'" in source
    assert "get_logger().info('正在快充...')" in source
    assert 'time.sleep(3.0)' in source
    assert 'response.success = True' in source
```

- [ ] **Step 2: Run and verify the missing-file failure**

Run:

```bash
python -m pytest test/test_charging_station_contract.py -q
```

Expected: one `FileNotFoundError` for `charging_station.py`.

- [ ] **Step 3: Implement the service node**

```python
"""Provide the simulated factory charging station service."""

import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger


class ChargingStation(Node):
    """Simulate a fixed-duration fast recharge."""

    def __init__(self):
        super().__init__('charging_station')
        self._service = self.create_service(
            Trigger, '/recharge', self._recharge_callback
        )
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
```

- [ ] **Step 4: Run and verify the service contract**

Run:

```bash
python -m pytest test/test_charging_station_contract.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit the charging station**

```bash
git add src/my_py_pkg/my_py_pkg/charging_station.py src/my_py_pkg/test/test_charging_station_contract.py
git commit -m "feat: add AGV charging station service"
```

### Task 3: Nav2 AGV Commander

**Files:**
- Create: `src/my_py_pkg/my_py_pkg/agv_commander.py`
- Create: `src/my_py_pkg/test/test_agv_commander_contract.py`

**Interfaces:**
- Consumes: `AgvWorkflow`, `PICKUP`, `DROPOFF`, `deplete_battery()`, and `should_interrupt_for_charge()`
- Produces: `AgvCommander(BasicNavigator)`
- Produces: `/burger_battery` publisher using `Float32`
- Consumes: `/recharge` service using `Trigger`
- Produces: `main(args=None) -> None`

- [ ] **Step 1: Write the failing commander contract tests**

```python
"""Static ROS contract checks that run without ROS on Windows."""

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'my_py_pkg'
    / 'agv_commander.py'
)


def test_commander_uses_required_nav2_topic_service_and_coordinates():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'class AgvCommander(BasicNavigator):' in source
    assert "node_name='agv_commander'" in source
    assert "create_publisher(Float32, '/burger_battery', 10)" in source
    assert "create_client(Trigger, '/recharge')" in source
    assert "PICKUP: (2.5, 1.0)" in source
    assert "DROPOFF: (0.0, 1.0)" in source
    assert "CHARGING: (0.0, 0.0)" in source


def test_commander_polls_nav2_and_handles_close_enough_arrival():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'while rclpy.ok() and not self.isTaskComplete():' in source
    assert 'feedback.distance_remaining < ARRIVAL_TOLERANCE' in source
    assert 'self.cancelTask()' in source
    assert 'TaskResult.SUCCEEDED' in source
    assert 'time.sleep(RETRY_DELAY)' in source


def test_commander_interrupts_recharges_and_resumes_saved_work():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'self._workflow.begin_recovery()' in source
    assert "self._navigate_to(CHARGING)" in source
    assert 'self._request_recharge()' in source
    assert 'self._workflow.complete_recharge()' in source
    assert 'self._battery_level = 100.0' in source
```

- [ ] **Step 2: Run and verify the missing-file failures**

Run:

```bash
python -m pytest test/test_agv_commander_contract.py -q
```

Expected: three `FileNotFoundError` failures for `agv_commander.py`.

- [ ] **Step 3: Implement the linear Simple Commander node**

```python
"""Run the factory AGV work, recharge, and interrupted-goal resume loop."""

import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from std_msgs.msg import Float32
from std_srvs.srv import Trigger

from my_py_pkg.agv_logic import (
    DROPOFF,
    PICKUP,
    AgvWorkflow,
    deplete_battery,
    should_interrupt_for_charge,
)


CHARGING = 'charging'
POSITIONS = {
    PICKUP: (2.5, 1.0),
    DROPOFF: (0.0, 1.0),
    CHARGING: (0.0, 0.0),
}
ARRIVAL_TOLERANCE = 0.25
BATTERY_PUBLISH_PERIOD = 1.0
RETRY_DELAY = 3.0


class AgvCommander(BasicNavigator):
    """Coordinate work goals, battery survival, charging, and resume."""

    def __init__(self):
        super().__init__(node_name='agv_commander')
        self._battery_publisher = self.create_publisher(
            Float32, '/burger_battery', 10
        )
        self._recharge_client = self.create_client(Trigger, '/recharge')
        self._workflow = AgvWorkflow()
        self._battery_level = 100.0
        now = time.monotonic()
        self._battery_updated_at = now
        self._battery_published_at = now
        self._publish_battery()

    def _pose_for(self, target: str) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x, pose.pose.position.y = POSITIONS[target]
        pose.pose.orientation.w = 1.0
        return pose

    def _publish_battery(self) -> None:
        message = Float32()
        message.data = float(self._battery_level)
        self._battery_publisher.publish(message)
        self._battery_published_at = time.monotonic()
        self.get_logger().info(f'当前电量: {self._battery_level:.1f}%')

    def _update_battery(self) -> bool:
        now = time.monotonic()
        self._battery_level = deplete_battery(
            self._battery_level, now - self._battery_updated_at
        )
        self._battery_updated_at = now
        if now - self._battery_published_at >= BATTERY_PUBLISH_PERIOD:
            self._publish_battery()
        return should_interrupt_for_charge(
            self._battery_level, self._workflow.recovering
        )

    def _navigate_to(self, target: str) -> str:
        x, y = POSITIONS[target]
        self.get_logger().info(
            f'下发导航目标 {target}: [{x:.1f}, {y:.1f}]'
        )
        self.goToPose(self._pose_for(target))
        close_enough = False

        while rclpy.ok() and not self.isTaskComplete():
            if self._update_battery() and self._workflow.begin_recovery():
                self.get_logger().warning(
                    f'电量 {self._battery_level:.1f}%：取消当前任务并返航充电'
                )
                self.cancelTask()
                return 'low_battery'

            feedback = self.getFeedback()
            if (
                feedback is not None
                and feedback.distance_remaining < ARRIVAL_TOLERANCE
            ):
                self.get_logger().info(
                    f'距离 {target} 小于 {ARRIVAL_TOLERANCE:.2f} 米，判定到达'
                )
                self.cancelTask()
                close_enough = True
                break

            time.sleep(0.05)

        if close_enough:
            return 'arrived'
        if not rclpy.ok():
            return 'stopped'

        result = self.getResult()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info(f'已到达 {target}')
            return 'arrived'

        self.get_logger().error(f'导航到 {target} 失败，3 秒后重试')
        self._pause_with_battery(RETRY_DELAY)
        return 'retry'

    def _pause_with_battery(self, duration: float) -> None:
        deadline = time.monotonic() + duration
        while rclpy.ok() and time.monotonic() < deadline:
            self._update_battery()
            time.sleep(0.05)

    def _request_recharge(self) -> bool:
        while rclpy.ok() and not self._recharge_client.wait_for_service(
            timeout_sec=1.0
        ):
            self._update_battery()
            self.get_logger().warning('/recharge 服务不可用，继续等待')

        if not rclpy.ok():
            return False

        self.get_logger().info('已抵达充电站，请求快速充电')
        future = self._recharge_client.call_async(Trigger.Request())
        while rclpy.ok() and not future.done():
            rclpy.spin_once(self, timeout_sec=0.1)
            self._update_battery()

        if not future.done():
            return False
        try:
            response = future.result()
        except Exception as error:
            self.get_logger().error(f'充电服务调用失败: {error}')
            self._pause_with_battery(RETRY_DELAY)
            return False
        if not response.success:
            self.get_logger().error(f'充电失败: {response.message}')
            self._pause_with_battery(RETRY_DELAY)
            return False

        resumed_target = self._workflow.complete_recharge()
        self._battery_level = 100.0
        self._battery_updated_at = time.monotonic()
        self._publish_battery()
        self.get_logger().info(
            f'充电完成，恢复被中断目标: {resumed_target}'
        )
        return True

    def run(self) -> None:
        """Wait for Nav2 and run the AGV state loop until shutdown."""
        self.get_logger().info('等待 Nav2 激活')
        self.waitUntilNav2Active()
        self.get_logger().info('Nav2 已激活，开始搬运循环')

        while rclpy.ok():
            if self._workflow.recovering:
                outcome = self._navigate_to(CHARGING)
                if outcome == 'arrived':
                    self._request_recharge()
                continue

            outcome = self._navigate_to(self._workflow.current_work_target)
            if outcome == 'arrived':
                next_target = self._workflow.complete_work_target()
                self.get_logger().info(f'切换下一搬运目标: {next_target}')


def main(args=None) -> None:
    """Run the AGV commander without a continuously spinning executor."""
    rclpy.init(args=args)
    commander = AgvCommander()
    try:
        commander.run()
    except KeyboardInterrupt:
        commander.get_logger().info('收到停止请求')
    finally:
        try:
            commander.cancelTask()
        except Exception:
            pass
        commander.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run the commander and pure-state tests**

Run:

```bash
python -m pytest test/test_agv_logic.py test/test_agv_commander_contract.py -q
```

Expected: `10 passed`.

- [ ] **Step 5: Run syntax compilation for all new modules**

Run:

```bash
python -m py_compile my_py_pkg/agv_logic.py my_py_pkg/agv_commander.py my_py_pkg/charging_station.py
```

Expected: exit code `0` with no output.

- [ ] **Step 6: Commit the commander**

```bash
git add src/my_py_pkg/my_py_pkg/agv_commander.py src/my_py_pkg/test/test_agv_commander_contract.py
git commit -m "feat: add resumable AGV commander"
```

### Task 4: Package Registration and Dependency

**Files:**
- Modify: `src/my_py_pkg/setup.py`
- Modify: `src/my_py_pkg/package.xml`
- Create: `src/my_py_pkg/test/test_agv_registration.py`

**Interfaces:**
- Consumes: `my_py_pkg.agv_commander:main`
- Consumes: `my_py_pkg.charging_station:main`
- Produces: `ros2 run my_py_pkg agv_commander`
- Produces: `ros2 run my_py_pkg charging_station`
- Declares: `nav2_simple_commander`

- [ ] **Step 1: Write the failing registration and dependency tests**

```python
"""Package registration checks for ROS 2 homework seven."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_agv_executables_are_registered():
    setup_source = (PACKAGE_ROOT / 'setup.py').read_text(encoding='utf-8')
    assert 'agv_commander = my_py_pkg.agv_commander:main' in setup_source
    assert (
        'charging_station = my_py_pkg.charging_station:main'
        in setup_source
    )


def test_nav2_simple_commander_dependency_is_declared():
    package_xml = (PACKAGE_ROOT / 'package.xml').read_text(encoding='utf-8')
    assert '<depend>nav2_simple_commander</depend>' in package_xml
```

- [ ] **Step 2: Run and verify two expected failures**

Run:

```bash
python -m pytest test/test_agv_registration.py -q
```

Expected: two assertion failures because the entries are absent.

- [ ] **Step 3: Register both console scripts**

Add these entries to the existing `console_scripts` list in `setup.py`:

```python
"agv_commander = my_py_pkg.agv_commander:main",
"charging_station = my_py_pkg.charging_station:main",
```

Do not remove or reorder existing entries.

- [ ] **Step 4: Declare the Nav2 Simple Commander dependency**

Add this beside the existing runtime `<depend>` elements in `package.xml`:

```xml
  <depend>nav2_simple_commander</depend>
```

The existing `rclpy`, `geometry_msgs`, `std_msgs`, and `std_srvs` declarations
already cover the other imports.

- [ ] **Step 5: Run the registration tests and full package test suite**

Run:

```bash
python -m pytest test/test_agv_registration.py -q
python -m pytest test -q
```

Expected: registration tests pass; full suite has zero failures, with the
existing copyright test still skipped.

- [ ] **Step 6: Commit package registration**

```bash
git add src/my_py_pkg/setup.py src/my_py_pkg/package.xml src/my_py_pkg/test/test_agv_registration.py
git commit -m "build: register AGV factory nodes"
```

### Task 5: Ubuntu Runbook and Final Local Verification

**Files:**
- Create: `docs/ros2-homework-7-runbook.md`

**Interfaces:**
- Documents: Ubuntu build, package tests, node startup, ROS graph inspection,
  battery/recharge observation, Nav2 parameter fallback, and acceptance checks.

- [ ] **Step 1: Write the runbook**

````markdown
# ROS 2 作业七运行与验证

## Ubuntu 构建

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select my_py_pkg --symlink-install
source install/setup.bash
colcon test --packages-select my_py_pkg
colcon test-result --verbose
```

## 启动顺序

先按 TurtleBot3 Jazzy 的环境配置启动 `turtlebot3_world`、定位与 Nav2。
在两个已加载工作空间环境的终端中分别运行：

```bash
ros2 run my_py_pkg charging_station
ros2 run my_py_pkg agv_commander
```

## 接口检查

```bash
ros2 topic info /burger_battery
ros2 topic echo /burger_battery
ros2 service type /recharge
ros2 service call /recharge std_srvs/srv/Trigger "{}"
```

预期话题类型为 `std_msgs/msg/Float32`，服务类型为
`std_srvs/srv/Trigger`。

## 仿真验收

1. Burger 首先前往取料区 `[2.5, 1.0]`。
2. 到站后在取料区与卸料区 `[0.0, 1.0]` 之间循环。
3. `/burger_battery` 从 `100.0` 开始，每秒下降约 `0.5`。
4. 电量不高于 `20.0` 时，当前目标被取消并保存。
5. Burger 前往充电站 `[0.0, 0.0]` 并调用 `/recharge`。
6. 充电站打印“正在快充...”，约 3 秒后返回成功。
7. 电量恢复到 `100.0`，Burger 返回被中断的工位。
8. 被中断目标完成后，正常搬运循环继续。

如果空旷通道仍出现 `Goal Aborted`，在实际加载的 TurtleBot3
`nav2_params.yaml` 中将全局和局部代价地图的 `inflation_radius`
适当减小，例如设为 `0.12`，然后重启 Nav2。不要修改
`build/`、`install/` 或 `log/` 中的生成副本。
````

- [ ] **Step 2: Run the full Windows-hosted verification**

Run from `src/my_py_pkg`:

```bash
python -m pytest test -q
python -m py_compile my_py_pkg/agv_logic.py my_py_pkg/agv_commander.py my_py_pkg/charging_station.py
```

Run from the repository root:

```bash
git diff --check
git status --short
git diff --stat origin/main...HEAD
```

Expected:

- all Python tests pass except the pre-existing intentional copyright skip;
- compilation exits `0` with no output;
- `git diff --check` prints nothing;
- only the design, plan, runbook, intended source, tests, and package metadata
  differ from `origin/main`.

- [ ] **Step 3: Commit the runbook**

```bash
git add docs/ros2-homework-7-runbook.md docs/superpowers/plans/2026-07-23-agv-battery-resume.md
git commit -m "docs: add AGV homework runbook"
```

### Task 6: GitHub Publication and Merge

**Files:**
- No source changes expected.

**Interfaces:**
- Produces: pushed branch `agent/agv-battery-resume`
- Produces: pull request targeting `main`
- Produces: merged `main`

- [ ] **Step 1: Verify GitHub CLI and authentication**

Run:

```bash
gh --version
gh auth status
```

Expected: an installed GitHub CLI and an authenticated account with access to
`amroyazed464-byte/ros2_ws`.

- [ ] **Step 2: Verify the branch immediately before publishing**

Run:

```bash
git status -sb
git log --oneline origin/main..HEAD
git diff --check origin/main...HEAD
```

Expected: clean branch, only task commits ahead of `origin/main`, and no
whitespace errors.

- [ ] **Step 3: Push with upstream tracking**

```bash
git push -u origin agent/agv-battery-resume
```

Expected: the remote branch is created without force-pushing.

- [ ] **Step 4: Create a ready pull request**

```powershell
$prBody = @'
## Summary

- add a Nav2 AGV commander with elapsed-time battery publication
- interrupt low-battery work, recharge through `/recharge`, and resume the saved goal
- add a standalone charging-station service and Windows-hosted contract tests

## Architecture

The commander uses Nav2 Simple Commander's linear polling model. It does not
wait for navigation from a timer callback or worker thread, avoiding nested
executor spinning.

## Validation

- `python -m pytest test -q`
- `python -m py_compile my_py_pkg/agv_logic.py my_py_pkg/agv_commander.py my_py_pkg/charging_station.py`
- `git diff --check`

Ubuntu 24.04, ROS 2 Jazzy, Nav2, and TurtleBot3 simulation remain runtime
verification steps unless their commands have also been run successfully.
'@

gh pr create `
  --base main `
  --head agent/agv-battery-resume `
  --title "feat: add resumable AGV battery workflow" `
  --body $prBody
```

The prepared body must describe:

- the two ROS nodes and pure state module;
- why a linear Simple Commander loop avoids nested executor failures;
- the battery interruption and resumed-goal behavior;
- Windows tests and syntax checks;
- the explicit limitation that Ubuntu ROS 2/Nav2 simulation remains to be
  verified if it has not been run.

Expected: a pull-request URL targeting `main`.

- [ ] **Step 5: Inspect the PR and merge**

```bash
gh pr checks --watch
gh pr merge --merge --delete-branch=false
```

Expected: required checks pass and the pull request reports as merged. Do not
delete the branch unless separately requested.

- [ ] **Step 6: Update local main and verify the merge**

```bash
git switch main
git pull --ff-only origin main
git log -1 --oneline --decorate
git status -sb
```

Expected: local `main` contains the merged change, matches `origin/main`, and
the working tree is clean.
