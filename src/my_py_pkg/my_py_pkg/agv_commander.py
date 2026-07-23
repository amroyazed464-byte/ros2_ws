"""Run the factory AGV work, recharge, and interrupted-goal resume loop."""

import time

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from std_msgs.msg import Float32
from std_srvs.srv import Trigger

from my_py_pkg.agv_logic import (
    DROPOFF,
    PICKUP,
    AgvWorkflow,
    LateGoalTracker,
    deplete_battery,
    distance_to_target,
    latch_recovery_for_battery,
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
FUTURE_POLL_PERIOD = 0.1
ACTION_SERVER_TIMEOUT = 5.0
ACTION_RESPONSE_TIMEOUT = 5.0
CANCEL_RESPONSE_TIMEOUT = 5.0
RECHARGE_RESPONSE_TIMEOUT = 10.0
SHUTDOWN_DRAIN_TIMEOUT = 5.0


class AgvCommander(BasicNavigator):
    """Coordinate work goals, battery survival, charging, and resume."""

    def __init__(self):
        super().__init__(node_name='agv_commander')
        self._battery_publisher = self.create_publisher(Float32, '/burger_battery', 10)
        self._recharge_client = self.create_client(Trigger, '/recharge')
        self._workflow = AgvWorkflow()
        self._late_goals = LateGoalTracker()
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

    def _begin_recovery_if_needed(self) -> bool:
        self._update_battery()
        return latch_recovery_for_battery(
            self._workflow, self._battery_level
        )

    def _service_late_goals(self) -> None:
        for event in self._late_goals.poll():
            if event.kind == 'response_rejected':
                self.get_logger().warning(
                    '超时后的导航目标响应最终被服务器拒绝'
                )
            elif event.kind == 'response_failed':
                self.get_logger().error(
                    f'超时后的导航目标响应失败: {event.detail}'
                )
            elif event.kind == 'accepted_cancel_requested':
                self.get_logger().warning(
                    '超时后的导航目标已被接受，已立即请求取消该目标'
                )
            elif event.kind == 'cancel_request_failed':
                self.get_logger().error(
                    f'超时目标的取消请求创建失败: {event.detail}'
                )
            elif event.kind == 'cancel_acknowledged':
                self.get_logger().info('超时目标的取消请求已确认')
                if event.handle is self.goal_handle:
                    self._clear_navigation()
            elif event.kind == 'cancel_rejected':
                self.get_logger().error('超时目标的取消请求未被接受')
            elif event.kind == 'cancel_failed':
                self.get_logger().error(
                    f'超时目标的取消响应失败: {event.detail}'
                )

    def _spin_once_with_late_cleanup(self, timeout: float) -> None:
        rclpy.spin_once(self, timeout_sec=timeout)
        self._service_late_goals()

    def _wait_for_future(
        self,
        future,
        timeout: float,
        allow_recovery: bool = True,
    ) -> tuple[bool, bool]:
        deadline = time.monotonic() + timeout
        recovery_started = False
        while rclpy.ok() and not future.done():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            self._spin_once_with_late_cleanup(
                min(FUTURE_POLL_PERIOD, remaining)
            )
            if allow_recovery:
                recovery_started = (
                    self._begin_recovery_if_needed() or recovery_started
                )
            else:
                self._update_battery()
        return future.done(), recovery_started

    def _clear_navigation(self) -> None:
        self.goal_handle = None
        self.result_future = None
        self.feedback = None

    def _cancel_navigation(self) -> tuple[bool, bool]:
        if self.goal_handle is None or self.result_future is None:
            self._clear_navigation()
            return True, False
        if self.result_future.done():
            self._clear_navigation()
            return True, False
        if self._late_goals.has_cancel_for(self.goal_handle):
            self.get_logger().warning(
                '当前导航目标的取消响应仍在等待'
            )
            return False, False

        try:
            cancel_future = self.goal_handle.cancel_goal_async()
        except Exception as error:
            self.get_logger().error(f'创建导航取消请求失败: {error}')
            return False, False

        response_ready, recovery_started = self._wait_for_future(
            cancel_future, CANCEL_RESPONSE_TIMEOUT
        )
        if not response_ready:
            self._late_goals.retain_cancel(
                self.goal_handle, cancel_future
            )
            self.get_logger().error(
                '导航取消响应超时；已保留该目标的取消 future 继续清理'
            )
            return False, recovery_started

        try:
            response = cancel_future.result()
        except Exception as error:
            self.get_logger().error(f'导航取消请求失败: {error}')
            return False, recovery_started
        if response is None or not response.goals_canceling:
            self.get_logger().error('导航取消请求未被接受')
            return False, recovery_started

        self._clear_navigation()
        return True, recovery_started

    def _pause_with_battery(self, duration: float) -> bool:
        deadline = time.monotonic() + duration
        recovery_started = False
        while rclpy.ok():
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            recovery_started = (
                self._begin_recovery_if_needed() or recovery_started
            )
            self._spin_once_with_late_cleanup(min(0.05, remaining))
        return recovery_started

    def _retry_after_error(self) -> str:
        recovery_started = self._pause_with_battery(RETRY_DELAY)
        return 'low_battery' if recovery_started else 'retry'

    def _submit_navigation(self, target: str) -> str:
        work_goal = target != CHARGING
        server_deadline = time.monotonic() + ACTION_SERVER_TIMEOUT
        while rclpy.ok():
            remaining = server_deadline - time.monotonic()
            if remaining <= 0.0:
                self.get_logger().error(
                    'navigate_to_pose 动作服务器等待超时'
                )
                return self._retry_after_error()
            if self.nav_to_pose_client.wait_for_server(
                timeout_sec=min(FUTURE_POLL_PERIOD, remaining)
            ):
                break
            self._spin_once_with_late_cleanup(0.0)
            if work_goal:
                if self._begin_recovery_if_needed():
                    return 'low_battery'
            else:
                self._update_battery()

        if not rclpy.ok():
            return 'stopped'
        if work_goal and self._begin_recovery_if_needed():
            return 'low_battery'

        goal = NavigateToPose.Goal()
        goal.pose = self._pose_for(target)
        goal.behavior_tree = ''
        self._clear_navigation()
        try:
            send_future = self.nav_to_pose_client.send_goal_async(
                goal, self._feedbackCallback
            )
        except Exception as error:
            self.get_logger().error(f'下发导航目标失败: {error}')
            return self._retry_after_error()

        response_ready, recovery_started = self._wait_for_future(
            send_future,
            ACTION_RESPONSE_TIMEOUT,
            allow_recovery=work_goal,
        )
        if not response_ready:
            if send_future.done():
                response_ready = True
            else:
                self._late_goals.retain_response(send_future)
                self.get_logger().error(
                    '导航目标响应超时；已保留 future 等待并清理迟到响应'
                )
                if recovery_started:
                    return 'low_battery'
                return self._retry_after_error()

        try:
            goal_handle = send_future.result()
        except Exception as error:
            self.get_logger().error(f'导航目标响应失败: {error}')
            if recovery_started:
                return 'low_battery'
            return self._retry_after_error()
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error(
                f'导航目标 {target} 被拒绝，{RETRY_DELAY:.0f} 秒后重试'
            )
            if recovery_started:
                return 'low_battery'
            return self._retry_after_error()

        self.goal_handle = goal_handle
        self.result_future = goal_handle.get_result_async()
        if recovery_started:
            canceled, _ = self._cancel_navigation()
            if not canceled:
                self.get_logger().error(
                    '低电量恢复已锁定，但新接受的工作目标取消失败'
                )
            return 'low_battery'
        return 'accepted'

    def _navigate_to(self, target: str) -> str:
        x, y = POSITIONS[target]
        if target != CHARGING and self._begin_recovery_if_needed():
            if self.goal_handle is not None:
                canceled, _ = self._cancel_navigation()
                if not canceled:
                    self.get_logger().error(
                        '低电量恢复已锁定，但遗留工作目标取消失败'
                    )
            self.get_logger().warning(
                f'电量 {self._battery_level:.1f}%：返航充电，不下发工作目标'
            )
            return 'low_battery'

        if self.goal_handle is not None:
            canceled, recovery_started = self._cancel_navigation()
            if recovery_started:
                return 'low_battery'
            if not canceled:
                return self._retry_after_error()

        self.get_logger().info(
            f'下发导航目标 {target}: [{x:.1f}, {y:.1f}]'
        )
        submission = self._submit_navigation(target)
        if submission != 'accepted':
            return submission

        while (
            rclpy.ok()
            and self.result_future is not None
            and not self.result_future.done()
        ):
            self._spin_once_with_late_cleanup(0.05)
            if self._begin_recovery_if_needed():
                self.get_logger().warning(
                    f'电量 {self._battery_level:.1f}%：取消当前任务并返航充电'
                )
                canceled, _ = self._cancel_navigation()
                if not canceled:
                    self.get_logger().error(
                        '低电量恢复已锁定，但工作目标取消失败'
                    )
                return 'low_battery'

            feedback = self.getFeedback()
            if feedback is not None:
                position = feedback.current_pose.pose.position
                distance = distance_to_target(position.x, position.y, x, y)
                if distance < ARRIVAL_TOLERANCE:
                    self.get_logger().info(
                        f'距离 {target} 小于 '
                        f'{ARRIVAL_TOLERANCE:.2f} 米，判定到达'
                    )
                    canceled, recovery_started = self._cancel_navigation()
                    if recovery_started:
                        return 'low_battery'
                    if not canceled:
                        return self._retry_after_error()
                    return 'arrived'

        if not rclpy.ok():
            return 'stopped'
        if self.result_future is None:
            return self._retry_after_error()

        try:
            result_message = self.result_future.result()
        except Exception as error:
            self.get_logger().error(f'导航结果读取失败: {error}')
            self._clear_navigation()
            return self._retry_after_error()
        if result_message is None:
            self.get_logger().error('导航结果为空')
            self._clear_navigation()
            return self._retry_after_error()

        self.status = result_message.status
        result = self.getResult()
        self._clear_navigation()
        if result == TaskResult.SUCCEEDED:
            self.get_logger().info(f'已到达 {target}')
            return 'arrived'

        self.get_logger().error(
            f'导航到 {target} 失败，{RETRY_DELAY:.0f} 秒后重试'
        )
        return self._retry_after_error()

    def _request_recharge(self) -> bool:
        while rclpy.ok() and not self._recharge_client.wait_for_service(
            timeout_sec=FUTURE_POLL_PERIOD
        ):
            self._spin_once_with_late_cleanup(0.0)
            self._update_battery()
            self.get_logger().warning('/recharge 服务不可用，继续等待')

        if not rclpy.ok():
            return False

        self.get_logger().info('已抵达充电站，请求快速充电')
        future = self._recharge_client.call_async(Trigger.Request())
        response_ready, _ = self._wait_for_future(future, RECHARGE_RESPONSE_TIMEOUT)
        if not response_ready:
            future.cancel()
            self.get_logger().error(
                '充电服务响应超时；本地服务等待已取消'
            )
            self._pause_with_battery(RETRY_DELAY)
            return False

        try:
            response = future.result()
        except Exception as error:
            self.get_logger().error(f'充电服务调用失败: {error}')
            self._pause_with_battery(RETRY_DELAY)
            return False
        if response is None or not response.success:
            message = '空响应' if response is None else response.message
            self.get_logger().error(f'充电失败: {message}')
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

    def _drain_late_goals(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        self._service_late_goals()
        for event in self._late_goals.retry_unresolved():
            if event.kind == 'cancel_retry_requested':
                self.get_logger().warning(
                    '关闭前已再次请求取消未解决的迟到目标'
                )
            else:
                self.get_logger().error(
                    f'关闭前重试迟到目标取消失败: {event.detail}'
                )
        while rclpy.ok() and self._late_goals.has_pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                break
            self._spin_once_with_late_cleanup(
                min(FUTURE_POLL_PERIOD, remaining)
            )
            self._update_battery()
        if (
            self._late_goals.has_pending
            or self._late_goals.unresolved_handle_count
        ):
            self.get_logger().error(
                '关闭前仍有未完成的迟到目标清理: '
                f'响应 {self._late_goals.pending_response_count}, '
                f'取消 {self._late_goals.pending_cancel_count}, '
                f'未解决句柄 {self._late_goals.unresolved_handle_count}'
            )

    def run(self) -> None:
        """Wait for Nav2 and run the AGV state loop until shutdown."""
        self.get_logger().info('等待 Nav2 激活')
        self.waitUntilNav2Active()
        activated_at = time.monotonic()
        self._battery_updated_at = activated_at
        self._battery_published_at = activated_at
        self._publish_battery()
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
        commander._cancel_navigation()
        commander._drain_late_goals(SHUTDOWN_DRAIN_TIMEOUT)
        commander.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
