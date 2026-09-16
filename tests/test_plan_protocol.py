"""Tests for the executable AI Native Plan protocol."""

import pytest

from tools.plan_protocol import PlanProtocolError, next_runnable_phase


def plan(state: str = "ready", precondition: str = "x") -> dict:
    """Build a compact Plan issue fixture."""
    return {
        "number": 40,
        "body": f"""## Plan
Protocol: 1
State: {state}

## Preconditions
- [{precondition}] main is green

## Phases
- [ ] #41 — contract
- [ ] #42 — engine

## Acceptance criteria
- [ ] propagation proven
""",
    }


def phase(number: int, state: str, blocked_by: str = "none", linked_pr: str = "none") -> dict:
    """Build a compact Phase issue fixture."""
    return {
        "number": number,
        "body": f"""Parent plan: #40
State: {state}
Blocked by: {blocked_by}
Linked PR: {linked_pr}

## Objective
Do the phase.
""",
    }


def test_selects_first_ready_phase_in_plan_order() -> None:
    """Plan order deterministically selects the first runnable Phase."""
    issues = [phase(41, "ready"), phase(42, "ready", "#41")]

    assert next_runnable_phase(plan(), issues) == 41


def test_dependency_requires_done_phase_not_merely_closed_issue() -> None:
    """Dependency evidence is semantic Phase completion, not issue closure alone."""
    first = phase(41, "verifying")
    first["state"] = "closed"
    issues = [first, phase(42, "ready", "#41")]

    assert next_runnable_phase(plan(), issues) is None


def test_done_dependency_unlocks_next_phase() -> None:
    """A Phase marked done satisfies an explicit dependency."""
    issues = [phase(41, "done"), phase(42, "ready", "#41")]

    assert next_runnable_phase(plan(), issues) == 42


def test_unchecked_plan_precondition_fails_closed() -> None:
    """Unchecked hard preconditions prevent execution."""
    issues = [phase(41, "ready"), phase(42, "ready", "#41")]

    assert next_runnable_phase(plan(precondition=" "), issues) is None


def test_active_linked_phase_is_reconciled_before_new_work() -> None:
    """An active linked PR keeps its Phase selected for reconciliation."""
    issues = [phase(41, "running", linked_pr="#46"), phase(42, "ready", "#41")]

    assert next_runnable_phase(plan(state="running"), issues) == 41


def test_multiple_active_phases_fail_closed() -> None:
    """Conflicting active Phase metadata cannot silently select new work."""
    issues = [
        phase(41, "running", linked_pr="#46"),
        phase(42, "verifying", "#41", "#47"),
    ]

    with pytest.raises(PlanProtocolError, match="multiple active linked phases"):
        next_runnable_phase(plan(state="running"), issues)


def test_wrong_parent_fails_closed() -> None:
    """A Phase cannot be reconstructed under a different parent Plan."""
    bad = phase(41, "ready")
    bad["body"] = bad["body"].replace("Parent plan: #40", "Parent plan: #99")

    with pytest.raises(PlanProtocolError, match="Parent plan"):
        next_runnable_phase(plan(), [bad, phase(42, "ready", "#41")])


def test_missing_phase_issue_fails_closed() -> None:
    """Incomplete GitHub reconstruction cannot produce runnable work."""
    with pytest.raises(PlanProtocolError, match="missing phase issue #42"):
        next_runnable_phase(plan(), [phase(41, "ready")])
