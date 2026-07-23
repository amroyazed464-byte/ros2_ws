"""Unit tests for AGV battery depletion and interrupted-goal memory."""

import gc
import weakref

import my_py_pkg.agv_logic as agv_logic
from my_py_pkg.agv_logic import (
    AgvWorkflow,
    deplete_battery,
    DROPOFF,
    PICKUP,
    should_interrupt_for_charge,
)
import pytest


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
    def __init__(
        self,
        accepted=True,
        cancel_future=None,
        result_future=None,
        cancel_error=None,
        result_error=None,
    ):
        self.accepted = accepted
        self.cancel_future = cancel_future or FakeFuture()
        self.result_future = result_future or FakeFuture()
        self.cancel_error = cancel_error
        self.result_error = result_error
        self.cancel_requests = 0
        self.result_requests = 0

    def cancel_goal_async(self):
        self.cancel_requests += 1
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.cancel_future

    def get_result_async(self):
        self.result_requests += 1
        if self.result_error is not None:
            raise self.result_error
        return self.result_future


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
    assert goal_handle.result_requests == 1
    assert tracker.pending_response_count == 0
    assert tracker.pending_cancel_count == 1
    assert tracker.pending_result_count == 1

    cancel_future.complete(FakeCancelResponse(accepted=True))
    events = tracker.poll()

    assert [event.kind for event in events] == ['cancel_acknowledged']
    assert events[0].handle is goal_handle
    assert tracker.has_pending is True

    goal_handle.result_future.complete(object())
    events = tracker.poll()

    assert [event.kind for event in events] == ['result_terminal']
    assert tracker.has_pending is False
    assert tracker.owns_handle(goal_handle) is False
    assert tracker.terminal_count == 1


def test_terminal_cleanup_releases_handle_and_bounds_diagnostics():
    tracker = agv_logic.LateGoalTracker()
    last_handle_ref = None

    for _ in range(tracker.TERMINAL_HISTORY_LIMIT + 5):
        handle = FakeGoalHandle()
        tracker.retain_result(handle, handle.result_future)
        handle.result_future.complete(object())
        assert [event.kind for event in tracker.poll()] == [
            'result_terminal'
        ]
        last_handle_ref = weakref.ref(handle)

    del handle
    gc.collect()

    assert last_handle_ref() is None
    assert tracker.terminal_count == tracker.TERMINAL_HISTORY_LIMIT + 5
    assert len(tracker.terminal_history) == tracker.TERMINAL_HISTORY_LIMIT
    assert all(isinstance(entry, str) for entry in tracker.terminal_history)


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


def test_exceptional_send_response_first_and_alone_is_cleaned_up():
    tracker = agv_logic.LateGoalTracker()
    failed_future = FakeFuture()
    tracker.retain_response(failed_future)
    failed_future.complete(error=RuntimeError('first response failed'))

    events = tracker.poll()

    assert [event.kind for event in events] == ['response_failed']
    assert events[0].detail == 'first response failed'
    assert tracker.pending_response_count == 0
    assert tracker.unresolved_handle_count == 0
    assert tracker.has_pending is False


def test_late_cancel_rejection_retains_the_exact_accepted_handle():
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

    assert [event.kind for event in events] == [
        'result_retry_requested',
        'cancel_retry_requested',
    ]
    assert tracker.unresolved_handle_count == 0
    assert tracker.pending_cancel_count == 1


def test_late_cancel_future_exception_retains_the_exact_handle():
    tracker = agv_logic.LateGoalTracker()
    cancel_future = FakeFuture()
    result_future = FakeFuture()
    goal_handle = FakeGoalHandle(
        cancel_future=cancel_future,
        result_future=result_future,
    )
    tracker.retain_cancel(goal_handle, cancel_future)
    tracker.retain_result(goal_handle, result_future)

    cancel_future.complete(error=RuntimeError('cancel response failed'))
    events = tracker.poll()

    assert [event.kind for event in events] == ['cancel_failed']
    assert tracker.unresolved_handles == (goal_handle,)
    assert tracker.owns_handle(goal_handle) is True


def test_late_cancel_request_creation_exception_retains_the_handle():
    tracker = agv_logic.LateGoalTracker()
    send_future = FakeFuture()
    goal_handle = FakeGoalHandle(
        cancel_error=RuntimeError('cannot create cancel request')
    )
    tracker.retain_response(send_future)
    send_future.complete(goal_handle)

    events = tracker.poll()

    assert [event.kind for event in events] == ['cancel_request_failed']
    assert tracker.unresolved_handles == (goal_handle,)
    assert tracker.pending_result_count == 1
    assert tracker.owns_handle(goal_handle) is True


def test_late_result_request_exception_keeps_handle_owned():
    tracker = agv_logic.LateGoalTracker()
    send_future = FakeFuture()
    goal_handle = FakeGoalHandle(
        result_error=RuntimeError('cannot request result')
    )
    tracker.retain_response(send_future)
    send_future.complete(goal_handle)

    events = tracker.poll()

    assert [event.kind for event in events] == [
        'result_request_failed',
        'accepted_cancel_requested',
    ]
    assert tracker.unresolved_handles == (goal_handle,)
    assert tracker.pending_cancel_count == 1
    assert tracker.owns_handle(goal_handle) is True


def test_empty_result_response_is_unresolved_not_terminal():
    tracker = agv_logic.LateGoalTracker()
    result_future = FakeFuture()
    goal_handle = FakeGoalHandle(result_future=result_future)
    tracker.retain_result(goal_handle, result_future)
    result_future.complete(None)

    events = tracker.poll()

    assert [event.kind for event in events] == ['result_failed']
    assert tracker.unresolved_handles == (goal_handle,)
    assert tracker.terminal_count == 0
    assert tracker.owns_handle(goal_handle) is True


def test_new_unresolved_during_drain_gets_only_one_retry():
    tracker = agv_logic.LateGoalTracker()
    first_cancel = FakeFuture()
    second_cancel = FakeFuture()
    result_future = FakeFuture()
    goal_handle = FakeGoalHandle(
        cancel_future=first_cancel,
        result_future=result_future,
    )
    tracker.retain_cancel(goal_handle, first_cancel)
    tracker.retain_result(goal_handle, result_future)

    first_cancel.complete(FakeCancelResponse(accepted=False))
    assert [event.kind for event in tracker.poll()] == ['cancel_rejected']

    goal_handle.cancel_future = second_cancel
    assert [event.kind for event in tracker.retry_unresolved()] == [
        'cancel_retry_requested'
    ]
    assert tracker.retry_unresolved() == []
    assert goal_handle.cancel_requests == 1

    second_cancel.complete(FakeCancelResponse(accepted=False))
    assert [event.kind for event in tracker.poll()] == ['cancel_rejected']
    assert tracker.retry_unresolved() == []
    assert tracker.unresolved_handles == (goal_handle,)


def test_pending_cancel_does_not_consume_the_shutdown_retry():
    tracker = agv_logic.LateGoalTracker()
    first_cancel = FakeFuture()
    result_future = FakeFuture()
    goal_handle = FakeGoalHandle(
        cancel_future=first_cancel,
        result_future=result_future,
    )
    tracker.retain_cancel(goal_handle, first_cancel)
    tracker.retain_result(goal_handle, result_future)
    tracker.mark_unresolved(goal_handle, 'cancel_timeout')

    assert tracker.retry_unresolved() == []
    assert tracker.has_retryable_unresolved is True

    first_cancel.complete(FakeCancelResponse(accepted=False))
    assert [event.kind for event in tracker.poll()] == ['cancel_rejected']
    goal_handle.cancel_future = FakeFuture()
    assert [event.kind for event in tracker.retry_unresolved()] == [
        'cancel_retry_requested'
    ]
