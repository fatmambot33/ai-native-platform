"""Tests for deterministic product-roadmap planning."""

import pytest

from tools.plan_protocol import PlanProtocolError
from tools.roadmap_engine import build_plan


def config() -> dict:
    """Return a compact roadmap policy for tests."""
    return {
        "version": 1,
        "candidate_labels": ["enhancement"],
        "priority_labels": {
            "roadmap:priority:p0": 0,
            "roadmap:priority:p1": 1,
            "roadmap:priority:p2": 2,
        },
        "capacity": {"now": 2, "next": 1},
        "managed_labels": {
            "now": "roadmap:now",
            "next": "roadmap:next",
            "later": "roadmap:later",
        },
        "dashboard": {
            "title": "[Roadmap] Product roadmap",
            "label": "roadmap",
            "marker": "<!-- ai-native-roadmap-dashboard -->",
        },
    }


def issue(number: int, severity: str, labels: list[str] | None = None, **extra) -> dict:
    """Build one GitHub-like issue fixture."""
    payload = {
        "number": number,
        "title": f"Issue {number}",
        "html_url": f"https://example.test/issues/{number}",
        "created_at": f"2026-08-{number:02d}T00:00:00Z",
        "labels": [{"name": value} for value in (labels or ["enhancement"])],
        "body": f"**Severity:** `{severity}`",
        "state": "open",
    }
    payload.update(extra)
    return payload


def plan_issue(state: str = "ready", precondition: str = "x") -> dict:
    """Build a versioned Plan with two ordered phases."""
    return issue(
        10,
        "high",
        body=(
            f"## Plan\nProtocol: 1\nState: {state}\n\n"
            "## Objective\nExecute the plan.\n\n"
            f"## Preconditions\n- [{precondition}] governance complete\n\n"
            "## Invariants\n- GitHub state is authoritative.\n\n"
            "## Phases\n- [ ] #11 first\n- [ ] #12 second\n\n"
            "## Acceptance criteria\n- [ ] Outcome verified.\n\n"
            "## Execution policy\nRun one phase at a time.\n"
        ),
    )


def phase_issue(
    number: int,
    *,
    state: str = "ready",
    blocked_by: str = "none",
    linked_pr: str = "none",
    issue_state: str = "open",
) -> dict:
    """Build one Phase issue for Plan #10."""
    return issue(
        number,
        "unknown",
        labels=["phase"],
        state=issue_state,
        body=(
            f"State: {state}\nParent plan: #10\n"
            f"Blocked by: {blocked_by}\nLinked PR: {linked_pr}\n\n"
            "## Objective\nDo the phase.\n\n"
            "## Scope\nKeep it focused.\n\n"
            "## Definition of done\n- [ ] Verified.\n\n"
            "## Deterministic validation\n- Run tests.\n"
        ),
    )


def pr_issue(number: int, state: str = "open") -> dict:
    """Build one GitHub PR issue record."""
    return issue(number, "unknown", labels=[], state=state, pull_request={"url": "pr"})


def test_build_plan_applies_capacity_and_human_priority() -> None:
    """Human priority wins, then severity, then age."""
    issues = [
        issue(1, "high"),
        issue(2, "critical", ["enhancement", "roadmap:priority:p1"]),
        issue(3, "low", ["enhancement", "roadmap:priority:p0"]),
        issue(4, "medium"),
    ]
    plan = build_plan(issues, config())
    assert [(item["number"], item["bucket"]) for item in plan["items"]] == [
        (3, "now"),
        (2, "now"),
        (1, "next"),
        (4, "later"),
    ]


def test_build_plan_ignores_prs_non_candidates_dashboard_and_closed() -> None:
    """Only open roadmap-candidate issues are included."""
    issues = [
        issue(1, "high"),
        issue(2, "high", ["bug"]),
        issue(3, "high", pull_request={"url": "https://example.test/pulls/3"}),
        issue(4, "high", body="<!-- ai-native-roadmap-dashboard -->\nGenerated dashboard"),
        issue(5, "critical", state="closed"),
    ]
    plan = build_plan(issues, config())
    assert [item["number"] for item in plan["items"]] == [1]
    assert "## Now" in plan["body"]
    assert "#1" in plan["body"]
    assert "linked pull-request state changes refresh the roadmap" in plan["body"]


def test_severity_label_overrides_body_severity() -> None:
    """Structured severity labels take precedence over body text."""
    issues = [issue(1, "low", ["enhancement", "severity:critical"]), issue(2, "high")]
    plan = build_plan(issues, config())
    assert plan["items"][0]["number"] == 1
    assert plan["items"][0]["severity"] == "critical"


def test_runnable_plan_consumes_capacity_and_exposes_phase_state() -> None:
    """A runnable Plan is scheduled with reconstructable execution metadata."""
    issues = [plan_issue(), phase_issue(11), phase_issue(12, blocked_by="#11")]
    plan = build_plan(issues, config())
    item = plan["items"][0]
    assert item["number"] == 10
    assert item["plan_state"] == "ready"
    assert item["phase_progress"] == "0/2"
    assert item["next_phase"] == 11
    assert "Plan `ready`, phases 0/2, next #11" in plan["body"]


def test_non_runnable_plan_does_not_consume_capacity() -> None:
    """A blocked Plan leaves Now capacity available to ordinary work."""
    issues = [
        plan_issue(state="blocked"),
        phase_issue(11, state="blocked"),
        phase_issue(12, state="blocked", blocked_by="#11"),
        issue(1, "medium"),
        issue(2, "low"),
    ]
    plan = build_plan(issues, config())
    assert [(item["number"], item["bucket"]) for item in plan["items"]] == [
        (1, "now"),
        (2, "now"),
    ]


def test_incomplete_draft_plan_is_non_runnable_without_breaking_roadmap() -> None:
    """Draft Plans may be incomplete and consume no capacity."""
    draft = issue(10, "high", body="## Plan\nProtocol: 1\nState: draft\n")
    plan = build_plan([draft, issue(1, "medium")], config())
    assert [item["number"] for item in plan["items"]] == [1]


def test_unsupported_plan_protocol_fails_closed() -> None:
    """Unknown Plan versions cannot fall through as ordinary candidates."""
    unsupported = plan_issue()
    unsupported["body"] = unsupported["body"].replace("Protocol: 1", "Protocol: 2")
    with pytest.raises(PlanProtocolError, match="unsupported Protocol"):
        build_plan([unsupported], config())


def test_closed_done_phase_can_unlock_next_phase() -> None:
    """Complete closed Phase state remains available to roadmap reconstruction."""
    issues = [
        plan_issue(state="running"),
        phase_issue(11, state="done", issue_state="closed"),
        phase_issue(12, blocked_by="#11"),
    ]
    plan = build_plan(issues, config())
    assert plan["items"][0]["next_phase"] == 12
    assert plan["items"][0]["phase_progress"] == "1/2"


def test_plan_checkbox_does_not_override_semantic_phase_state() -> None:
    """Dashboard progress comes from Phase state, not stale Plan checkboxes."""
    stale = plan_issue(state="running")
    stale["body"] = stale["body"].replace("- [ ] #11 first", "- [x] #11 first")
    issues = [stale, phase_issue(11), phase_issue(12, blocked_by="#11")]
    plan = build_plan(issues, config())
    assert plan["items"][0]["phase_progress"] == "0/2"
    assert plan["items"][0]["next_phase"] == 11


def test_non_phase_checkbox_reference_does_not_affect_progress() -> None:
    """Only references in the Phases section contribute to Plan reconstruction."""
    candidate = plan_issue()
    candidate["body"] = candidate["body"].replace(
        "- [x] governance complete", "- [x] #99 governance complete"
    )
    issues = [candidate, phase_issue(11), phase_issue(12, blocked_by="#11")]
    plan = build_plan(issues, config())
    assert plan["items"][0]["phase_progress"] == "0/2"
    assert plan["items"][0]["next_phase"] == 11


def test_open_linked_pr_is_reconciled_despite_stale_phase_state() -> None:
    """An actual open PR prevents advancement even if Phase text says done."""
    issues = [
        plan_issue(state="running"),
        phase_issue(11, state="done", linked_pr="#46"),
        phase_issue(12, blocked_by="#11"),
        pr_issue(46),
    ]
    plan = build_plan(issues, config())
    assert plan["items"][0]["next_phase"] == 11


def test_invalid_plan_metadata_fails_closed() -> None:
    """Malformed versioned Plans are rejected rather than scheduled as ordinary work."""
    issues = [plan_issue(state="ready", precondition=" "), phase_issue(11), phase_issue(12)]
    plan = build_plan(issues, config())
    assert plan["items"] == []

    malformed = plan_issue()
    malformed["body"] = malformed["body"].replace("State: ready", "State: nonsense")
    with pytest.raises(PlanProtocolError, match="invalid State"):
        build_plan([malformed, phase_issue(11), phase_issue(12)], config())


def test_missing_mandatory_plan_section_fails_closed() -> None:
    """A ready Plan missing its contract cannot consume roadmap capacity."""
    incomplete = plan_issue()
    incomplete["body"] = incomplete["body"].replace(
        "## Invariants\n- GitHub state is authoritative.\n\n", ""
    )
    with pytest.raises(PlanProtocolError, match="missing section: Invariants"):
        build_plan([incomplete, phase_issue(11), phase_issue(12)], config())
