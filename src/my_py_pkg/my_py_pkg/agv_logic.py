"""Pure state transitions for the factory AGV demonstration."""

from dataclasses import dataclass, field
import math


PICKUP = 'pickup'
DROPOFF = 'dropoff'


def deplete_battery(
    level: float,
    elapsed_seconds: float,
    rate_per_second: float = 0.5,
) -> float:
    """Decrease a battery level according to elapsed monotonic time."""
    if elapsed_seconds < 0.0:
        raise ValueError('elapsed_seconds must not be negative')
    if rate_per_second <= 0.0:
        raise ValueError('rate_per_second must be greater than zero')
    return max(0.0, min(100.0, level - elapsed_seconds * rate_per_second))


def should_interrupt_for_charge(
    level: float,
    recovering: bool,
    threshold: float = 20.0,
) -> bool:
    """Return whether low battery should start a new recovery cycle."""
    return not recovering and level <= threshold


def distance_to_target(
    current_x: float,
    current_y: float,
    target_x: float,
    target_y: float,
) -> float:
    """Return planar distance from a current position to one exact target."""
    return math.hypot(target_x - current_x, target_y - current_y)


@dataclass
class AgvWorkflow:
    """Remember the work target across a charging interruption."""

    current_work_target: str = PICKUP
    interrupted_target: str | None = None
    recovering: bool = False

    def begin_recovery(self) -> bool:
        """Latch recovery and preserve the current work target once."""
        if self.recovering:
            return False
        self.interrupted_target = self.current_work_target
        self.recovering = True
        return True

    def complete_recharge(self) -> str:
        """Restore and return the work target saved before charging."""
        if not self.recovering or self.interrupted_target is None:
            raise RuntimeError('cannot complete recharge without an interrupted goal')
        self.current_work_target = self.interrupted_target
        self.interrupted_target = None
        self.recovering = False
        return self.current_work_target

    def complete_work_target(self) -> str:
        """Advance to the opposite station after a work goal completes."""
        if self.recovering:
            raise RuntimeError('cannot complete a work target during recovery')
        self.current_work_target = (
            DROPOFF if self.current_work_target == PICKUP else PICKUP
        )
        return self.current_work_target


def latch_recovery_for_battery(
    workflow: AgvWorkflow,
    battery_level: float,
) -> bool:
    """Latch low-battery recovery while preserving the active work target."""
    if not should_interrupt_for_charge(battery_level, workflow.recovering):
        return False
    return workflow.begin_recovery()


@dataclass(frozen=True)
class LateGoalEvent:
    """Describe one completed late goal-response cleanup transition."""

    kind: str
    handle: object | None = None
    detail: str = ''


@dataclass
class _GoalOwnership:
    handle: object
    cancel_future: object | None = None
    result_future: object | None = None
    unresolved_reasons: set[str] = field(default_factory=set)
    retry_attempted: bool = False
    cancel_acknowledged: bool = False
    result_terminal: bool = False


class LateGoalTracker:
    """Own every accepted late handle until its result is terminal."""

    _CANCEL_REASONS = {
        'cancel_request_failed',
        'cancel_failed',
        'cancel_rejected',
        'cancel_timeout',
    }
    _RESULT_REASONS = {'result_request_failed', 'result_failed'}

    def __init__(self):
        self._responses = []
        self._goals = []
        self._terminal_handles = []

    @property
    def pending_response_count(self) -> int:
        """Return the number of send-goal responses still pending."""
        return len(self._responses)

    @property
    def pending_cancel_count(self) -> int:
        """Return the number of goal-specific cancellations still pending."""
        return sum(goal.cancel_future is not None for goal in self._goals)

    @property
    def pending_result_count(self) -> int:
        """Return the number of terminal result responses still pending."""
        return sum(goal.result_future is not None for goal in self._goals)

    @property
    def has_pending(self) -> bool:
        """Return whether any future still needs executor progress."""
        return bool(
            self._responses
            or self.pending_cancel_count
            or self.pending_result_count
        )

    @property
    def unresolved_handles(self) -> tuple:
        """Return deduplicated accepted handles needing cleanup retry."""
        return tuple(
            goal.handle
            for goal in self._goals
            if goal.unresolved_reasons
        )

    @property
    def unresolved_handle_count(self) -> int:
        """Return the count of accepted handles needing cleanup retry."""
        return len(self.unresolved_handles)

    @property
    def has_retryable_unresolved(self) -> bool:
        """Return whether shutdown still owes a retry to any handle."""
        return any(
            goal.unresolved_reasons and not goal.retry_attempted
            for goal in self._goals
        )

    def _find_goal(self, handle):
        for goal in self._goals:
            if goal.handle is handle:
                return goal
        return None

    def _goal_for(self, handle) -> _GoalOwnership:
        goal = self._find_goal(handle)
        if goal is None:
            goal = _GoalOwnership(handle)
            self._goals.append(goal)
        return goal

    def owns_handle(self, handle) -> bool:
        """Return whether a handle is cleanup-owned or terminal history."""
        return (
            self._find_goal(handle) is not None
            or any(existing is handle for existing in self._terminal_handles)
        )

    def mark_unresolved(self, handle, reason: str) -> None:
        """Deduplicate ownership for one accepted handle and failure reason."""
        self._goal_for(handle).unresolved_reasons.add(reason)

    def retain_response(self, future) -> None:
        """Retain one timed-out send-goal response future."""
        if not any(existing is future for existing in self._responses):
            self._responses.append(future)

    def retain_cancel(self, handle, future) -> None:
        """Retain cancellation ownership for one exact goal handle."""
        goal = self._goal_for(handle)
        goal.cancel_future = future
        goal.unresolved_reasons.difference_update(self._CANCEL_REASONS)

    def retain_result(self, handle, future) -> None:
        """Retain the result future that removes Jazzy feedback state."""
        goal = self._goal_for(handle)
        goal.result_future = future
        goal.unresolved_reasons.difference_update(self._RESULT_REASONS)

    def has_cancel_for(self, handle) -> bool:
        """Return whether cancellation is already pending for this handle."""
        goal = self._find_goal(handle)
        return goal is not None and goal.cancel_future is not None

    def ensure_result(self, handle) -> list[LateGoalEvent]:
        """Request and retain terminal result cleanup for one handle."""
        goal = self._goal_for(handle)
        if goal.result_future is not None or goal.result_terminal:
            return []
        try:
            result_future = handle.get_result_async()
        except Exception as error:
            self.mark_unresolved(handle, 'result_request_failed')
            return [
                LateGoalEvent(
                    'result_request_failed',
                    handle=handle,
                    detail=str(error),
                )
            ]
        self.retain_result(handle, result_future)
        return []

    def mark_cancel_acknowledged(self, handle) -> None:
        """Record cancellation acknowledgement for one exact handle."""
        goal = self._goal_for(handle)
        goal.cancel_acknowledged = True
        goal.cancel_future = None
        goal.unresolved_reasons.difference_update(self._CANCEL_REASONS)

    def _finish_if_terminal(self, goal: _GoalOwnership) -> None:
        if not goal.result_terminal or goal.cancel_future is not None:
            return
        if goal in self._goals:
            self._goals.remove(goal)
        if not any(
            existing is goal.handle for existing in self._terminal_handles
        ):
            self._terminal_handles.append(goal.handle)

    def poll(self) -> list[LateGoalEvent]:
        """Advance completed late responses without blocking."""
        events = []

        pending_responses = []
        for future in self._responses:
            if not future.done():
                pending_responses.append(future)
                continue
            try:
                handle = future.result()
            except Exception as error:
                events.append(
                    LateGoalEvent('response_failed', detail=str(error))
                )
                continue
            if handle is None or not handle.accepted:
                events.append(LateGoalEvent('response_rejected'))
                continue

            events.extend(self.ensure_result(handle))
            try:
                cancel_future = handle.cancel_goal_async()
            except Exception as error:
                self.mark_unresolved(handle, 'cancel_request_failed')
                events.append(
                    LateGoalEvent(
                        'cancel_request_failed',
                        handle=handle,
                        detail=str(error),
                    )
                )
                continue
            self.retain_cancel(handle, cancel_future)
            events.append(
                LateGoalEvent('accepted_cancel_requested', handle=handle)
            )
        self._responses = pending_responses

        for goal in list(self._goals):
            cancel_future = goal.cancel_future
            if cancel_future is not None and cancel_future.done():
                goal.cancel_future = None
                try:
                    response = cancel_future.result()
                except Exception as error:
                    self.mark_unresolved(goal.handle, 'cancel_failed')
                    events.append(
                        LateGoalEvent(
                            'cancel_failed',
                            handle=goal.handle,
                            detail=str(error),
                        )
                    )
                else:
                    if response is not None and response.goals_canceling:
                        self.mark_cancel_acknowledged(goal.handle)
                        events.append(
                            LateGoalEvent(
                                'cancel_acknowledged',
                                handle=goal.handle,
                            )
                        )
                    else:
                        self.mark_unresolved(
                            goal.handle, 'cancel_rejected'
                        )
                        events.append(
                            LateGoalEvent(
                                'cancel_rejected',
                                handle=goal.handle,
                            )
                        )

            result_future = goal.result_future
            if result_future is not None and result_future.done():
                goal.result_future = None
                try:
                    result_future.result()
                except Exception as error:
                    self.mark_unresolved(goal.handle, 'result_failed')
                    events.append(
                        LateGoalEvent(
                            'result_failed',
                            handle=goal.handle,
                            detail=str(error),
                        )
                    )
                else:
                    goal.result_terminal = True
                    goal.unresolved_reasons.clear()
                    events.append(
                        LateGoalEvent(
                            'result_terminal',
                            handle=goal.handle,
                        )
                    )
            self._finish_if_terminal(goal)
        return events

    def retry_unresolved(self) -> list[LateGoalEvent]:
        """Retry result and cancellation once per unresolved handle."""
        events = []
        for goal in list(self._goals):
            if not goal.unresolved_reasons or goal.retry_attempted:
                continue
            retry_attempted = False

            if goal.result_future is None and not goal.result_terminal:
                retry_attempted = True
                try:
                    result_future = goal.handle.get_result_async()
                except Exception as error:
                    self.mark_unresolved(
                        goal.handle, 'result_request_failed'
                    )
                    events.append(
                        LateGoalEvent(
                            'result_retry_failed',
                            handle=goal.handle,
                            detail=str(error),
                        )
                    )
                else:
                    self.retain_result(goal.handle, result_future)
                    events.append(
                        LateGoalEvent(
                            'result_retry_requested',
                            handle=goal.handle,
                        )
                    )

            if (
                goal.cancel_future is None
                and not goal.cancel_acknowledged
                and not goal.result_terminal
            ):
                retry_attempted = True
                try:
                    cancel_future = goal.handle.cancel_goal_async()
                except Exception as error:
                    self.mark_unresolved(
                        goal.handle, 'cancel_request_failed'
                    )
                    events.append(
                        LateGoalEvent(
                            'cancel_retry_failed',
                            handle=goal.handle,
                            detail=str(error),
                        )
                    )
                else:
                    self.retain_cancel(goal.handle, cancel_future)
                    events.append(
                        LateGoalEvent(
                            'cancel_retry_requested',
                            handle=goal.handle,
                        )
                    )
            if retry_attempted:
                goal.retry_attempted = True
        return events
