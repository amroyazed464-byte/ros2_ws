"""Unit tests for AGV battery depletion and interrupted-goal memory."""

import pytest

import my_py_pkg.agv_logic as agv_logic
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


def test_distance_to_target_uses_xy_euclidean_distance():
    assert agv_logic.distance_to_target(0.0, 0.0, 3.0, 4.0) == 5.0
    assert agv_logic.distance_to_target(2.5, 1.0, 2.5, 1.0) == 0.0


def test_low_battery_latches_the_current_target_once():
    workflow = AgvWorkflow(current_work_target=DROPOFF)

    assert agv_logic.latch_recovery_for_battery(workflow, 20.1) is False
    assert agv_logic.latch_recovery_for_battery(workflow, 20.0) is True
    assert workflow.interrupted_target == DROPOFF
    assert agv_logic.latch_recovery_for_battery(workflow, 10.0) is False


class FakeFuture:
    def __init__(self):
        self._done = False
        self._result = None
        self._error = None

    def done(self):
        return self._done

    def result(self):
        if self._error is not None:
            raise self._error
        return self._result

    def complete(self, result=None, error=None):
        self._result = result
        self._error = error
        self._done = True


class FakeGoalHandle:
    def __init__(self, accepted=True, cancel_future=None):
        self.accepted = accepted
        self.cancel_future = cancel_future or FakeFuture()
        self.cancel_requests = 0

    def cancel_goal_async(self):
        self.cancel_requests += 1
        return self.cancel_future


class FakeCancelResponse:
    def __init__(self, accepted):
        self.goals_canceling = [object()] if accepted else []


def test_late_goal_tracker_retains_pending_response_until_completion():
    tracker = agv_logic.LateGoalTracker()
    send_future = FakeFuture()

    tracker.retain_response(send_future)

    assert tracker.poll() == []
    assert tracker.pending_response_count == 1
    assert tracker.has_pending is True


def test_late_accepted_goal_is_canceled_and_acknowledged():
    tracker = agv_logic.LateGoalTracker()
    send_future = FakeFuture()
    cancel_future = FakeFuture()
    goal_handle = FakeGoalHandle(cancel_future=cancel_future)
    tracker.retain_response(send_future)

    send_future.complete(goal_handle)
    events = tracker.poll()

    assert [event.kind for event in events] == ['accepted_cancel_requested']
    assert events[0].handle is goal_handle
    assert goal_handle.cancel_requests == 1
    assert tracker.pending_response_count == 0
    assert tracker.pending_cancel_count == 1

    cancel_future.complete(FakeCancelResponse(accepted=True))
    events = tracker.poll()

    assert [event.kind for event in events] == ['cancel_acknowledged']
    assert events[0].handle is goal_handle
    assert tracker.has_pending is False


def test_late_rejection_and_response_exception_are_cleaned_up():
    tracker = agv_logic.LateGoalTracker()
    rejected_future = FakeFuture()
    failed_future = FakeFuture()
    tracker.retain_response(rejected_future)
    tracker.retain_response(failed_future)

    rejected_future.complete(FakeGoalHandle(accepted=False))
    failed_future.complete(error=RuntimeError('late response failed'))
    events = tracker.poll()

    assert [event.kind for event in events] == [
        'response_rejected',
        'response_failed',
    ]
    assert events[1].detail == 'late response failed'
    assert tracker.has_pending is False


def test_late_cancel_failure_is_reported_and_cleaned_up():
    tracker = agv_logic.LateGoalTracker()
    cancel_future = FakeFuture()
    goal_handle = FakeGoalHandle(cancel_future=cancel_future)
    tracker.retain_cancel(goal_handle, cancel_future)

    cancel_future.complete(FakeCancelResponse(accepted=False))
    events = tracker.poll()

    assert [event.kind for event in events] == ['cancel_rejected']
    assert events[0].handle is goal_handle
    assert tracker.unresolved_handle_count == 1
    assert tracker.has_pending is False

    retry_future = FakeFuture()
    goal_handle.cancel_future = retry_future
    events = tracker.retry_unresolved()

    assert [event.kind for event in events] == ['cancel_retry_requested']
    assert tracker.unresolved_handle_count == 0
    assert tracker.pending_cancel_count == 1
