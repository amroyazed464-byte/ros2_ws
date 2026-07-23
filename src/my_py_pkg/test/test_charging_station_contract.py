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
    assert "get_logger().info('姝ｅ湪蹇厖...')" in source
    assert 'time.sleep(3.0)' in source
    assert 'response.success = True' in source
