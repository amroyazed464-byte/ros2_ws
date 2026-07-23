"""Unit tests for AGV battery depletion and interrupted-goal memory."""

import pytest

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
