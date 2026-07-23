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
