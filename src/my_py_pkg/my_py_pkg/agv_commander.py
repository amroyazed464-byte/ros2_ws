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
        self._battery_publisher = self.create_publisher(Float32, '/burger_battery', 10)
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

        self.get_logger().error(f'导航到 {target} 失败，{RETRY_DELAY:.0f} 秒后重试')
        self._pause_with_battery(RETRY_DELAY)
        return 'retry'

    def _pause_with_battery(self, duration: float) -> None:
        deadline = time.monotonic() + duration
        while rclpy.ok():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            self._update_battery()
            time.sleep(min(0.05, remaining))

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
