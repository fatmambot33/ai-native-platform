"""Build a deterministic Now/Next/Later product roadmap from GitHub issues."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from tools.plan_protocol import PlanProtocolError, next_runnable_phase

SEVERITY_PATTERN = re.compile(r"\*\*Severity:\*\*\s*`?(critical|high|medium|low)`?", re.I)
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
PLAN_PROTOCOL_PATTERN = re.compile(r"^Protocol:\s*1\s*$", re.M)
PLAN_STATE_PATTERN = re.compile(r"^State:\s*(draft|ready|running|blocked|verifying|done)\s*$", re.M)
PHASE_PATTERN = re.compile(r"^- \[([ xX])\] #(\d+)\b", re.M)


@dataclass(frozen=True)
class RoadmapItem:
    """One issue assigned to a product-roadmap horizon."""

    number: int
    title: str
    url: str
    severity: str
    bucket: str
    label: str
    plan_state: str | None = None
    phase_progress: str | None = None
    next_phase: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def _label_names(issue: dict[str, Any]) -> set[str]:
    """Normalize GitHub issue labels to a set of names."""
    names: set[str] = set()
    for label in issue.get("labels", []):
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and label.get("name"):
            names.add(str(label["name"]))
    return names


def _severity(issue: dict[str, Any]) -> str:
    """Extract the normalized severity from labels or the issue body."""
    labels = _label_names(issue)
    for severity in ("critical", "high", "medium", "low"):
        if f"severity:{severity}" in labels:
            return severity
    body = str(issue.get("body") or "")
    match = SEVERITY_PATTERN.search(body)
    return match.group(1).lower() if match else "unknown"


def _manual_priority(issue: dict[str, Any], config: dict[str, Any]) -> int:
    """Return the explicit human priority, or the default unprioritized rank."""
    labels = _label_names(issue)
    priorities = config.get("priority_labels", {})
    matches = [int(rank) for label, rank in priorities.items() if label in labels]
    return min(matches) if matches else len(priorities)


def _is_plan(issue: dict[str, Any]) -> bool:
    """Return whether an issue declares the versioned Plan protocol."""
    return PLAN_PROTOCOL_PATTERN.search(str(issue.get("body") or "")) is not None


def _is_candidate(issue: dict[str, Any], config: dict[str, Any]) -> bool:
    """Return whether an issue belongs in the automated execution roadmap."""
    if str(issue.get("state") or "open") != "open" or issue.get("pull_request"):
        return False
    body = str(issue.get("body") or "")
    marker = str(config.get("dashboard", {}).get("marker", ""))
    if marker and marker in body:
        return False
    candidate_labels = set(config.get("candidate_labels", []))
    return bool(_label_names(issue) & candidate_labels)


def _issue_sort_key(issue: dict[str, Any], config: dict[str, Any]) -> tuple[Any, ...]:
    """Return the deterministic priority key for one roadmap candidate."""
    severity = _severity(issue)
    created_at = str(issue.get("created_at") or "9999-12-31T23:59:59Z")
    return (
        _manual_priority(issue, config),
        SEVERITY_RANK.get(severity, SEVERITY_RANK["unknown"]),
        created_at,
        int(issue.get("number", 0)),
    )


def _plan_metadata(issue: dict[str, Any], issues: list[dict[str, Any]]) -> tuple[str, str, int | None]:
    """Return validated state, phase progress, and next runnable Phase for a Plan."""
    body = str(issue.get("body") or "")
    state_match = PLAN_STATE_PATTERN.search(body)
    if state_match is None:
        raise PlanProtocolError(f"plan #{issue['number']} has invalid State")
    phases = PHASE_PATTERN.findall(body)
    if not phases:
        raise PlanProtocolError(f"plan #{issue['number']} has no phases")
    completed = sum(mark.lower() == "x" for mark, _ in phases)
    progress = f"{completed}/{len(phases)}"
    return state_match.group(1), progress, next_runnable_phase(issue, issues)


def build_plan(issues: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic roadmap plan from GitHub issues.

    Versioned Plans consume capacity only when their protocol state reconstructs
    successfully and exposes a runnable or already-active Phase.
    """
    candidates: list[tuple[dict[str, Any], tuple[str, str, int | None] | None]] = []
    for issue in issues:
        if not _is_candidate(issue, config):
            continue
        metadata = _plan_metadata(issue, issues) if _is_plan(issue) else None
        if metadata is not None and metadata[2] is None:
            continue
        candidates.append((issue, metadata))
    candidates.sort(key=lambda pair: _issue_sort_key(pair[0], config))

    capacity = config.get("capacity", {})
    now_limit = max(0, int(capacity.get("now", 3)))
    next_limit = max(0, int(capacity.get("next", 5)))
    labels = config.get("managed_labels", {})

    items: list[RoadmapItem] = []
    for index, (issue, metadata) in enumerate(candidates):
        bucket = "now" if index < now_limit else "next" if index < now_limit + next_limit else "later"
        plan_state, phase_progress, next_phase = metadata or (None, None, None)
        items.append(RoadmapItem(number=int(issue["number"]), title=str(issue.get("title") or f"Issue #{issue['number']}"), url=str(issue.get("html_url") or ""), severity=_severity(issue), bucket=bucket, label=str(labels[bucket]), plan_state=plan_state, phase_progress=phase_progress, next_phase=next_phase))

    return {"version": int(config.get("version", 1)), "managed_labels": labels, "priority_labels": config.get("priority_labels", {}), "dashboard": config.get("dashboard", {}), "items": [item.as_dict() for item in items], "body": render_dashboard(items, config)}


def render_dashboard(items: list[RoadmapItem], config: dict[str, Any]) -> str:
    """Render the managed roadmap dashboard issue body."""
    dashboard = config.get("dashboard", {})
    marker = str(dashboard.get("marker", "<!-- ai-native-roadmap-dashboard -->"))
    priorities = ", ".join(f"`{label}`" for label in config.get("priority_labels", {}))
    lines = [marker, "# Product roadmap", "", "This issue is maintained automatically from open roadmap candidates.", "The human strategy remains in `ROADMAP.md`; this is the live execution view.", "", f"Human priority overrides: {priorities or 'none configured'}.", "Within the same priority, higher severity and older issues run first."]
    for bucket, heading in (("now", "Now"), ("next", "Next"), ("later", "Later")):
        lines.extend(["", f"## {heading}", ""])
        selected = [item for item in items if item.bucket == bucket]
        if not selected:
            lines.append("- No active items.")
            continue
        for item in selected:
            link = f"[{item.title}]({item.url})" if item.url else item.title
            detail = f" — `{item.severity}`"
            if item.plan_state is not None:
                detail += f" — Plan `{item.plan_state}`, phases {item.phase_progress}, next #{item.next_phase}"
            lines.append(f"- #{item.number} {link}{detail}")
    lines.extend(["", "## Policy", "", "- Only open issues with a configured candidate label are managed.", "- Pull requests and this dashboard issue are excluded.", "- Plans consume execution capacity only while they expose a runnable Phase.", "- Invalid Plan metadata fails closed instead of being scheduled.", "- Opening, closing, reopening, editing, or changing labels refreshes the roadmap.", "- Automation only changes roadmap labels and this dashboard issue."])
    return "\n".join(lines) + "\n"


def load_config(path: Path) -> dict[str, Any]:
    """Load and minimally validate the roadmap policy file."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("roadmap config must be a mapping")
    for bucket in ("now", "next", "later"):
        if bucket not in payload.get("managed_labels", {}):
            raise ValueError(f"managed_labels.{bucket} is required")
    return payload


def main() -> int:
    """CLI entry point used by the roadmap workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    issues = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("roadmap input must contain a list of GitHub issues")
    plan = build_plan(issues, load_config(args.config))
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
