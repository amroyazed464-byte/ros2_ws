"""Static ROS contract checks that run without ROS on Windows."""

from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'my_py_pkg'
    / 'agv_commander.py'
)
RUNBOOK = REPOSITORY / 'docs' / 'ros2-homework-7-runbook.md'


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
    assert 'feedback.current_pose.pose.position' in source
    assert 'distance_to_target(' in source
    assert 'feedback.distance_remaining' not in source
    assert 'self._cancel_navigation()' in source
    assert 'TaskResult.SUCCEEDED' in source
    assert 'self._pause_with_battery(RETRY_DELAY)' in source


def test_commander_interrupts_recharges_and_resumes_saved_work():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'latch_recovery_for_battery(' in source
    assert "self._navigate_to(CHARGING)" in source
    assert 'self._request_recharge()' in source
    assert 'self._workflow.complete_recharge()' in source
    assert 'self._battery_level = 100.0' in source


def test_retry_pause_surfaces_low_battery_recovery_before_resubmission():
    source = SOURCE.read_text(encoding='utf-8')
    navigate = source[
        source.index('    def _navigate_to('):
        source.index('    def _request_recharge(')
    ]
    pause = source[
        source.index('    def _pause_with_battery('):
        source.index('    def _request_recharge(')
    ]

    preflight = navigate.index(
        'if target != CHARGING and self._begin_recovery_if_needed():'
    )
    submit = navigate.index('submission = self._submit_navigation(target)')
    preflight_recovery = navigate[preflight:submit]

    assert preflight < submit
    assert (
        'if target != CHARGING and self._begin_recovery_if_needed():\n'
        '            if self.goal_handle is not None:'
        in preflight_recovery
    )
    assert 'self._cancel_navigation()' in preflight_recovery
    assert 'def _pause_with_battery(self, duration: float) -> bool:' in pause
    assert 'self._begin_recovery_if_needed()' in pause
    assert 'return recovery_started' in pause
    assert (
        "return 'low_battery' if recovery_started else 'retry'"
        in source
    )
    assert 'return self._retry_after_error()' in navigate


def test_navigation_submission_and_cancellation_are_bounded():
    source = SOURCE.read_text(encoding='utf-8')

    assert 'from nav2_msgs.action import NavigateToPose' in source
    assert 'ACTION_RESPONSE_TIMEOUT =' in source
    assert 'CANCEL_RESPONSE_TIMEOUT =' in source
    assert 'def _submit_navigation(self, target: str) -> str:' in source
    assert 'self.nav_to_pose_client.send_goal_async(' in source
    assert 'self._feedbackCallback' in source
    assert 'def _cancel_navigation(self) -> tuple[bool, bool]:' in source
    assert 'self.goal_handle.cancel_goal_async()' in source
    assert 'def _wait_for_future(' in source
    assert 'deadline = time.monotonic() + timeout' in source
    assert 'rclpy.spin_once(self, timeout_sec=' in source
    assert 'self.goToPose(' not in source
    assert 'self.cancelTask(' not in source
    assert 'spin_until_future_complete' not in source


def test_timed_out_goal_response_is_retained_and_late_goals_are_drained():
    source = SOURCE.read_text(encoding='utf-8')
    submit = source[
        source.index('    def _submit_navigation('):
        source.index('    def _navigate_to(')
    ]
    main = source[source.index('def main('):]

    assert 'if send_future.done():' in submit
    assert 'self._late_goals.retain_response(send_future)' in submit
    assert 'send_future.cancel()' not in source
    assert 'def _service_late_goals(self) -> None:' in source
    assert 'def _drain_late_goals(self, timeout: float) -> None:' in source
    assert 'commander._drain_late_goals(SHUTDOWN_DRAIN_TIMEOUT)' in main
    assert 'abandoned = cancel_future.cancel()' not in source
    assert 'abandoned = future.cancel()' not in source


def test_current_goal_result_creation_failure_transfers_owned_handle():
    source = SOURCE.read_text(encoding='utf-8')
    submit = source[
        source.index('    def _submit_navigation('):
        source.index('    def _navigate_to(')
    ]
    cancel = source[
        source.index('    def _cancel_navigation('):
        source.index('    def _pause_with_battery(')
    ]

    assert 'try:\n            self.result_future = ' in submit
    assert 'goal_handle.get_result_async()' in submit
    assert 'except Exception as error:' in submit
    assert 'self._cancel_navigation()' in submit
    assert 'if self.goal_handle is None:' in cancel
    assert (
        'if self.goal_handle is None or self.result_future is None:'
        not in cancel
    )
    assert 'try:\n                self.result_future.result()' in cancel
    assert "'result_failed'" in cancel
    assert 'self._transfer_current_to_late_cleanup(' in cancel


def test_shutdown_interleaves_new_unresolved_retry_with_drain():
    source = SOURCE.read_text(encoding='utf-8')
    drain = source[
        source.index('    def _drain_late_goals('):
        source.index('    def run(')
    ]

    retry = drain.index('self._late_goals.retry_unresolved()')
    poll = drain.index('self._service_late_goals()')
    loop = drain.index('while rclpy.ok()')
    assert loop < poll < retry
    assert 'has_retryable_unresolved' in drain


def test_all_linear_wait_paths_service_late_goal_cleanup():
    source = SOURCE.read_text(encoding='utf-8')
    wait = source[
        source.index('    def _wait_for_future('):
        source.index('    def _clear_navigation(')
    ]
    pause = source[
        source.index('    def _pause_with_battery('):
        source.index('    def _retry_after_error(')
    ]

    assert 'self._spin_once_with_late_cleanup(' in wait
    assert 'self._spin_once_with_late_cleanup(' in pause
    assert 'time.sleep(' not in pause


def test_close_enough_distance_is_scoped_to_the_current_target():
    source = SOURCE.read_text(encoding='utf-8')
    navigate = source[
        source.index('    def _navigate_to('):
        source.index('    def _request_recharge(')
    ]

    assert 'position = feedback.current_pose.pose.position' in navigate
    assert 'distance_to_target(position.x, position.y, x, y)' in navigate
    assert 'feedback.distance_remaining' not in navigate


def test_recharge_response_has_a_bounded_recovery_preserving_timeout():
    source = SOURCE.read_text(encoding='utf-8')
    recharge = source[
        source.index('    def _request_recharge('):
        source.index('    def run(')
    ]

    assert 'RECHARGE_RESPONSE_TIMEOUT = 10.0' in source
    assert (
        'self._wait_for_future(future, RECHARGE_RESPONSE_TIMEOUT)'
        in recharge
    )
    assert 'future.cancel()' in recharge
    timeout = recharge.index('if not response_ready:')
    retry = recharge.index('self._pause_with_battery(RETRY_DELAY)', timeout)
    failure = recharge.index('return False', retry)
    recharge_completion = recharge.index(
        'self._workflow.complete_recharge()'
    )
    assert timeout < retry < failure < recharge_completion


def test_runbook_starts_commander_with_simulation_time():
    runbook = RUNBOOK.read_text(encoding='utf-8')
    assert (
        'ros2 run my_py_pkg agv_commander '
        '--ros-args -p use_sim_time:=true'
        in runbook
    )


def test_battery_operation_starts_after_nav2_activation():
    source = SOURCE.read_text(encoding='utf-8')
    run = source[source.index('    def run('):source.index('\ndef main(')]

    wait_for_nav2 = run.index('self.waitUntilNav2Active()')
    activation_time = run.index('activated_at = time.monotonic()')
    reset_update = run.index('self._battery_updated_at = activated_at')
    reset_publish = run.index('self._battery_published_at = activated_at')
    initial_publish = run.index('self._publish_battery()')
    work_loop = run.index('while rclpy.ok():')

    assert (
        wait_for_nav2
        < activation_time
        < reset_update
        < reset_publish
        < initial_publish
        < work_loop
    )
