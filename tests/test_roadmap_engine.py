"""Tests for deterministic product-roadmap planning."""

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
    }
    payload.update(extra)
    return payload


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


def test_build_plan_ignores_prs_non_candidates_and_dashboard() -> None:
    """Only open roadmap-candidate issues are included."""
    issues = [
        issue(1, "high"),
        issue(2, "high", ["bug"]),
        issue(3, "high", pull_request={"url": "https://example.test/pulls/3"}),
        issue(
            4,
            "high",
            body="<!-- ai-native-roadmap-dashboard -->\nGenerated dashboard",
        ),
    ]

    plan = build_plan(issues, config())

    assert [item["number"] for item in plan["items"]] == [1]
    assert "## Now" in plan["body"]
    assert "#1" in plan["body"]
    assert "changing labels refreshes the roadmap" in plan["body"]


def test_severity_label_overrides_body_severity() -> None:
    """Structured severity labels take precedence over body text."""
    issues = [
        issue(1, "low", ["enhancement", "severity:critical"]),
        issue(2, "high"),
    ]

    plan = build_plan(issues, config())

    assert plan["items"][0]["number"] == 1
    assert plan["items"][0]["severity"] == "critical"
