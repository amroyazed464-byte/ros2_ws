"""Behavioral accepted-goal ownership tests without ROS installed."""

import importlib
import sys
from types import ModuleType, SimpleNamespace

from my_py_pkg.agv_logic import LateGoalTracker
import pytest


class FakeFuture:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def done(self):
        return True

    def result(self):
        if self._error is not None:
            raise self._error
        return self._result


class FakeGoalHandle:
    accepted = True

    def __init__(self):
        self.cancel_requests = 0

    def cancel_goal_async(self):
        self.cancel_requests += 1
        return FakeFuture(SimpleNamespace(goals_canceling=[self]))


class FakeLogger:
    def error(self, _message):
        pass

    def warning(self, _message):
        pass

    def info(self, _message):
        pass


def _install_module(monkeypatch, name, **attributes):
    module = ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_commander(monkeypatch):
    rclpy = _install_module(
        monkeypatch,
        'rclpy',
        ok=lambda: True,
        spin_once=lambda *_args, **_kwargs: None,
        init=lambda **_kwargs: None,
        shutdown=lambda: None,
    )
    rclpy.node = _install_module(
        monkeypatch, 'rclpy.node', Node=object
    )
    geometry_msgs = _install_module(monkeypatch, 'geometry_msgs')
    geometry_msgs.msg = _install_module(
        monkeypatch, 'geometry_msgs.msg', PoseStamped=object
    )
    nav2_msgs = _install_module(monkeypatch, 'nav2_msgs')
    nav2_msgs.action = _install_module(
        monkeypatch,
        'nav2_msgs.action',
        NavigateToPose=SimpleNamespace(Goal=object),
    )
    nav2_simple = _install_module(
        monkeypatch, 'nav2_simple_commander'
    )
    nav2_simple.robot_navigator = _install_module(
        monkeypatch,
        'nav2_simple_commander.robot_navigator',
        BasicNavigator=object,
        TaskResult=SimpleNamespace(SUCCEEDED=1),
    )
    std_msgs = _install_module(monkeypatch, 'std_msgs')
    std_msgs.msg = _install_module(
        monkeypatch, 'std_msgs.msg', Float32=object
    )
    std_srvs = _install_module(monkeypatch, 'std_srvs')
    std_srvs.srv = _install_module(
        monkeypatch,
        'std_srvs.srv',
        Trigger=SimpleNamespace(Request=object),
    )
    monkeypatch.delitem(
        sys.modules, 'my_py_pkg.agv_commander', raising=False
    )
    module = importlib.import_module('my_py_pkg.agv_commander')
    sys.modules.pop('my_py_pkg.agv_commander', None)
    return module


@pytest.mark.parametrize(
    'result_future',
    [
        FakeFuture(error=RuntimeError('result transport failed')),
        FakeFuture(result=None),
    ],
)
def test_bad_current_result_is_canceled_and_transferred_for_retry(
    monkeypatch,
    result_future,
):
    module = _load_commander(monkeypatch)
    commander = module.AgvCommander.__new__(module.AgvCommander)
    handle = FakeGoalHandle()
    commander.goal_handle = handle
    commander.result_future = result_future
    commander.feedback = object()
    commander._late_goals = LateGoalTracker()
    commander.get_logger = lambda: FakeLogger()
    commander._wait_for_future = lambda *_args: (True, False)

    outcome, result_message, recovery_started = (
        commander._consume_current_result()
    )

    assert outcome == 'retry'
    assert result_message is None
    assert recovery_started is False
    assert handle.cancel_requests == 1
    assert commander.goal_handle is None
    assert commander._late_goals.owns_handle(handle) is True
    assert (
        commander._late_goals.pending_result_count
        or commander._late_goals.unresolved_handle_count
    )
