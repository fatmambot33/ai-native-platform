"""Tests for the executable AI Native Plan protocol."""

import pytest

from tools.plan_protocol import PlanProtocolError, next_runnable_phase


def plan(state: str = "ready", precondition: str = "x") -> dict:
    """Build a compact valid Plan issue fixture."""
    return {
        "number": 40,
        "body": f"""## Plan
Protocol: 1
State: {state}

## Objective
Prove executable planning.

## Preconditions
- [{precondition}] main is green

## Invariants
- GitHub state is authoritative.

## Phases
- [ ] #41 — contract
- [ ] #42 — engine

## Acceptance criteria
- [ ] propagation proven

## Execution policy
Run one phase at a time.
""",
    }


def phase(
    number: int,
    state: str,
    blocked_by: str = "none",
    linked_pr: str = "none",
    issue_state: str = "open",
) -> dict:
    """Build a compact valid Phase issue fixture."""
    return {
        "number": number,
        "state": issue_state,
        "body": f"""Parent plan: #40
State: {state}
Blocked by: {blocked_by}
Linked PR: {linked_pr}

## Objective
Do the phase.

## Scope
Keep the change focused.

## Definition of done
- [ ] Outcome verified.

## Deterministic validation
- Run tests.
""",
    }


def pull_request(number: int, state: str = "open") -> dict:
    """Build a GitHub PR issue record."""
    return {"number": number, "state": state, "pull_request": {"url": "pr"}}


def test_selects_first_ready_phase_in_plan_order() -> None:
    """Plan order deterministically selects the first runnable Phase."""
    issues = [phase(41, "ready"), phase(42, "ready", "#41")]
    assert next_runnable_phase(plan(), issues) == 41


def test_phase_references_are_scoped_to_phases_section() -> None:
    """Issue references in other checkbox sections are not child Phases."""
    candidate = plan()
    candidate["body"] = candidate["body"].replace(
        "- [x] main is green", "- [x] #99 governance is complete"
    )
    issues = [phase(41, "ready"), phase(42, "ready", "#41")]
    assert next_runnable_phase(candidate, issues) == 41


def test_dependency_requires_done_phase_not_merely_closed_issue() -> None:
    """Closed Phase issues fail closed unless semantically done."""
    issues = [phase(41, "verifying", issue_state="closed"), phase(42, "ready", "#41")]
    with pytest.raises(PlanProtocolError, match="closed phase #41"):
        next_runnable_phase(plan(), issues)


def test_done_dependency_unlocks_next_phase() -> None:
    """A Phase marked done satisfies an explicit dependency."""
    issues = [phase(41, "done", issue_state="closed"), phase(42, "ready", "#41")]
    assert next_runnable_phase(plan(), issues) == 42


def test_unchecked_plan_precondition_fails_closed() -> None:
    """Unchecked hard preconditions prevent execution."""
    issues = [phase(41, "ready"), phase(42, "ready", "#41")]
    assert next_runnable_phase(plan(precondition=" "), issues) is None


def test_active_linked_pr_is_reconciled_before_new_work() -> None:
    """Actual open PR state keeps its Phase selected despite stale Phase state."""
    issues = [
        phase(41, "done", linked_pr="#46"),
        phase(42, "ready", "#41"),
        pull_request(46),
    ]
    assert next_runnable_phase(plan(state="running"), issues) == 41


def test_closed_linked_pr_does_not_remain_active() -> None:
    """A closed linked PR does not block a semantically completed Phase."""
    issues = [
        phase(41, "done", linked_pr="#46", issue_state="closed"),
        phase(42, "ready", "#41"),
        pull_request(46, state="closed"),
    ]
    assert next_runnable_phase(plan(state="running"), issues) == 42


def test_missing_linked_pr_fails_closed() -> None:
    """Linked PR metadata must resolve from reconstructed GitHub state."""
    issues = [phase(41, "running", linked_pr="#46"), phase(42, "ready", "#41")]
    with pytest.raises(PlanProtocolError, match="missing PR #46"):
        next_runnable_phase(plan(state="running"), issues)


def test_multiple_active_phases_fail_closed() -> None:
    """Conflicting semantic or PR activity cannot silently select new work."""
    issues = [
        phase(41, "running", linked_pr="#46"),
        phase(42, "verifying", "#41", "#47"),
        pull_request(46),
        pull_request(47),
    ]
    with pytest.raises(PlanProtocolError, match="multiple active phases"):
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


def test_missing_mandatory_plan_section_fails_closed() -> None:
    """Executable Plans must satisfy the complete documented contract."""
    incomplete = plan()
    incomplete["body"] = incomplete["body"].replace(
        "## Invariants\n- GitHub state is authoritative.\n\n", ""
    )
    with pytest.raises(PlanProtocolError, match="missing section: Invariants"):
        next_runnable_phase(incomplete, [phase(41, "ready"), phase(42, "ready", "#41")])


def test_draft_plan_may_be_incomplete() -> None:
    """Draft is explicitly allowed to represent an incomplete contract."""
    draft = {"number": 40, "body": "## Plan\nProtocol: 1\nState: draft\n"}
    assert next_runnable_phase(draft, []) is None
