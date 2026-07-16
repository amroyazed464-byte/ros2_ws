"""Static contract tests that can run without importing ROS on Windows."""

from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / 'my_py_pkg'


def test_battery_uses_required_topic_message_and_parameters():
    """The battery node exposes the agreed ROS topic and parameters."""
    source = (PACKAGE / 'battery.py').read_text(encoding='utf-8')
    assert "super().__init__('battery')" in source
    assert "create_publisher(Int32, '/battery_level'" in source
    assert "declare_parameter('initial_level', 100)" in source
    assert "declare_parameter('update_period', 1.0)" in source
    assert "declare_parameter('step', 10)" in source


def test_led_panel_uses_required_topic_and_four_led_payload():
    """The panel translates battery levels into the agreed LED array."""
    source = (PACKAGE / 'led_panel.py').read_text(encoding='utf-8')
    assert "super().__init__('led_panel')" in source
    assert 'create_subscription(' in source
    assert "Int32, '/battery_level', self._battery_callback" in source
    assert 'create_publisher(' in source
    assert "UInt8MultiArray, '/led_panel', qos" in source
    assert 'message.data = [0, 0, 0, int(self._led3_on)]' in source
