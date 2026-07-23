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
    assert 'self._pause_with_battery(RETRY_DELAY)' in source


def test_commander_interrupts_recharges_and_resumes_saved_work():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'self._workflow.begin_recovery()' in source
    assert "self._navigate_to(CHARGING)" in source
    assert 'self._request_recharge()' in source
    assert 'self._workflow.complete_recharge()' in source
    assert 'self._battery_level = 100.0' in source


def test_commander_clears_feedback_and_retries_a_rejected_goal():
    source = SOURCE.read_text(encoding='utf-8')
    navigate = source[
        source.index('    def _navigate_to('):
        source.index('    def _pause_with_battery(')
    ]

    reset_feedback = navigate.index('self.feedback = None')
    send_goal = navigate.index(
        'goal_accepted = self.goToPose(self._pose_for(target))'
    )
    rejection = navigate.index('if not goal_accepted:')
    retry_delay = navigate.index(
        'self._pause_with_battery(RETRY_DELAY)', rejection
    )
    retry_return = navigate.index("return 'retry'", retry_delay)
    poll_goal = navigate.index(
        'while rclpy.ok() and not self.isTaskComplete():'
    )

    assert reset_feedback < send_goal < rejection
    assert rejection < retry_delay < retry_return < poll_goal


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
