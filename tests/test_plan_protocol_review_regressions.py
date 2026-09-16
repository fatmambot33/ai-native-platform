"""Regression tests for Plan protocol review invariants."""

import pytest

from tools.plan_protocol import PlanProtocolError, next_runnable_phase
from tools.roadmap_engine import build_plan


def plan_body(state: str = "running") -> str:
    """Return a complete two-Phase Plan body."""
    return f"""## Plan
Protocol: 1
State: {state}

## Objective
Execute safely.

## Preconditions
- [x] ready

## Invariants
- One phase at a time.

## Phases
- [ ] #41 first
- [ ] #42 second

## Acceptance criteria
- [ ] verified

## Execution policy
Run serially.
"""


def phase(number: int, state: str, blocked_by: str = "none") -> dict:
    """Return a complete Phase issue."""
    return {
        "number": number,
        "state": "open",
        "body": f"""Parent plan: #40
State: {state}
Blocked by: {blocked_by}
Linked PR: none

## Objective
Do it.

## Scope
Focused.

## Definition of done
- [ ] verified

## Deterministic validation
- pytest
""",
    }


def test_running_phase_without_pr_remains_active() -> None:
    """Semantic activity prevents concurrent Phase selection without a PR."""
    plan = {"number": 40, "body": plan_body()}
    assert next_runnable_phase(plan, [phase(41, "running"), phase(42, "ready")]) == 41


def test_duplicate_phases_section_fails_closed() -> None:
    """Duplicate mandatory sections cannot hide work."""
    candidate = {"number": 40, "body": plan_body() + "\n## Phases\n- [ ] #43 hidden\n"}
    with pytest.raises(PlanProtocolError, match="duplicate section: Phases"):
        next_runnable_phase(candidate, [phase(41, "ready"), phase(42, "ready")])


def test_completed_external_dependency_unlocks_phase() -> None:
    """Closed completion evidence outside the current Plan satisfies a blocker."""
    candidate = {"number": 40, "body": plan_body()}
    external = {"number": 99, "state": "closed", "body": "State: done"}
    issues = [phase(41, "done"), phase(42, "ready", "#99"), external]
    issues[0]["state"] = "closed"
    assert next_runnable_phase(candidate, issues) == 42


def roadmap_config() -> dict:
    """Return minimal roadmap configuration."""
    return {
        "version": 1,
        "candidate_labels": ["enhancement"],
        "priority_labels": {},
        "capacity": {"now": 1, "next": 0},
        "managed_labels": {
            "now": "roadmap:now",
            "next": "roadmap:next",
            "later": "roadmap:later",
        },
        "dashboard": {"marker": "<!-- dashboard -->"},
    }


def roadmap_issue(number: int, body: str) -> dict:
    """Return one open roadmap candidate."""
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": body,
        "state": "open",
        "labels": [{"name": "enhancement"}],
    }


def test_protocol_text_outside_plan_heading_is_ordinary_issue() -> None:
    """Incidental Protocol text does not opt an issue into Plan parsing."""
    ordinary = roadmap_issue(1, "Proposal example:\nProtocol: HTTP/2")
    result = build_plan([ordinary], roadmap_config())
    assert [item["number"] for item in result["items"]] == [1]


def test_blocked_plan_stays_visible_without_capacity() -> None:
    """Non-runnable Plans remain observable but do not take a horizon slot."""
    blocked = roadmap_issue(40, plan_body(state="blocked"))
    phases = [phase(41, "blocked"), phase(42, "blocked")]
    ordinary = roadmap_issue(1, "ordinary")
    result = build_plan([blocked, *phases, ordinary], roadmap_config())
    assert [item["number"] for item in result["items"]] == [1]
    assert result["inactive_plans"] == [
        {
            "number": 40,
            "title": "Issue 40",
            "url": "",
            "state": "blocked",
            "phase_progress": "0/2",
        }
    ]
    assert "Plans outside capacity" in result["body"]
    assert "Plan `blocked`, phases 0/2" in result["body"]
