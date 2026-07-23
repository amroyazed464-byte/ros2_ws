"""Pure state transitions for the factory AGV demonstration."""

from dataclasses import dataclass
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


class LateGoalTracker:
    """Own timed-out goal responses and their specific cancel futures."""

    def __init__(self):
        self._responses = []
        self._cancellations = []
        self._unresolved_handles = []

    @property
    def pending_response_count(self) -> int:
        """Return the number of send-goal responses still pending."""
        return len(self._responses)

    @property
    def pending_cancel_count(self) -> int:
        """Return the number of goal-specific cancellations still pending."""
        return len(self._cancellations)

    @property
    def has_pending(self) -> bool:
        """Return whether any late response or cancellation remains owned."""
        return bool(self._responses or self._cancellations)

    @property
    def unresolved_handle_count(self) -> int:
        """Return late accepted handles whose cancellation failed."""
        return len(self._unresolved_handles)

    def retain_response(self, future) -> None:
        """Retain one timed-out send-goal response future."""
        if not any(existing is future for existing in self._responses):
            self._responses.append(future)

    def retain_cancel(self, handle, future) -> None:
        """Retain cancellation ownership for one exact goal handle."""
        self._unresolved_handles = [
            existing
            for existing in self._unresolved_handles
            if existing is not handle
        ]
        if not any(
            existing_handle is handle
            for existing_handle, _ in self._cancellations
        ):
            self._cancellations.append((handle, future))

    def has_cancel_for(self, handle) -> bool:
        """Return whether cancellation is already pending for this handle."""
        return any(
            existing_handle is handle
            for existing_handle, _ in self._cancellations
        )

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
                self._unresolved_handles.append(handle)
                events.append(
                    LateGoalEvent('response_failed', detail=str(error))
                )
                continue
            if handle is None or not handle.accepted:
                events.append(LateGoalEvent('response_rejected'))
                continue
            try:
                cancel_future = handle.cancel_goal_async()
            except Exception as error:
                self._unresolved_handles.append(handle)
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

        pending_cancellations = []
        for handle, future in self._cancellations:
            if not future.done():
                pending_cancellations.append((handle, future))
                continue
            try:
                response = future.result()
            except Exception as error:
                events.append(
                    LateGoalEvent(
                        'cancel_failed',
                        handle=handle,
                        detail=str(error),
                    )
                )
                continue
            if response is not None and response.goals_canceling:
                events.append(
                    LateGoalEvent('cancel_acknowledged', handle=handle)
                )
            else:
                self._unresolved_handles.append(handle)
                events.append(
                    LateGoalEvent('cancel_rejected', handle=handle)
                )
        self._cancellations = pending_cancellations
        return events

    def retry_unresolved(self) -> list[LateGoalEvent]:
        """Retry cancellation once for each known unresolved late handle."""
        events = []
        handles = self._unresolved_handles
        self._unresolved_handles = []
        for handle in handles:
            try:
                cancel_future = handle.cancel_goal_async()
            except Exception as error:
                self._unresolved_handles.append(handle)
                events.append(
                    LateGoalEvent(
                        'cancel_retry_failed',
                        handle=handle,
                        detail=str(error),
                    )
                )
                continue
            self.retain_cancel(handle, cancel_future)
            events.append(
                LateGoalEvent('cancel_retry_requested', handle=handle)
            )
        return events
