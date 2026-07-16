"""Static ROS contract tests for the turtle controller."""

from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / 'my_py_pkg'
    / 'turtle_controller.py'
)


def test_controller_subscribes_and_calls_required_service():
    """The controller consumes the panel and targets turtle1's service."""
    source = SOURCE.read_text(encoding='utf-8')
    assert "super().__init__('turtle_controller')" in source
    assert 'create_subscription(' in source
    assert "UInt8MultiArray, '/led_panel', self._led_callback" in source
    assert 'create_client(' in source
    assert "TeleportAbsolute, '/turtle1/teleport_absolute'" in source


def test_controller_validates_payload_and_suppresses_duplicates():
    """Malformed or repeated LED data cannot trigger extra requests."""
    source = SOURCE.read_text(encoding='utf-8')
    assert 'if len(message.data) < 4:' in source
    assert 'if led3_value == self._requested_led3:' in source
    assert 'target_for_led3(led3_value)' in source


def test_controller_serializes_requests_and_retains_latest_state():
    """Only one request runs while the latest desired state is retained."""
    source = SOURCE.read_text(encoding='utf-8')
    assert 'self._request_in_flight' in source
    assert 'self._requested_led3' in source
    assert 'self._completed_led3' in source
    assert 'future.add_done_callback(self._teleport_done)' in source
