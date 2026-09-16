"""Parse and select executable AI Native Plan phases from GitHub issues."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_FIELD_RE = re.compile(r"^(Protocol|State|Parent plan|Blocked by|Linked PR):\s*(.+?)\s*$", re.M)
_PHASE_RE = re.compile(r"^- \[[ xX]\] #(\d+)\b", re.M)
_REF_RE = re.compile(r"#(\d+)")
_PLAN_STATES = {"draft", "ready", "running", "blocked", "verifying", "done"}
_PHASE_STATES = {"ready", "running", "blocked", "verifying", "done"}
_ACTIVE_PHASE_STATES = {"running", "verifying"}
_REQUIRED_PLAN_SECTIONS = (
    "Plan",
    "Objective",
    "Preconditions",
    "Invariants",
    "Phases",
    "Acceptance criteria",
    "Execution policy",
)
_REQUIRED_PHASE_SECTIONS = (
    "Objective",
    "Scope",
    "Definition of done",
    "Deterministic validation",
)


class PlanProtocolError(ValueError):
    """Raised when GitHub issue metadata violates the Plan protocol."""


@dataclass(frozen=True)
class PhaseState:
    """Normalized execution state for one Phase issue."""

    number: int
    state: str
    blockers: tuple[int, ...]
    linked_pr: int | None


def _fields(body: str) -> dict[str, str]:
    """Return protocol metadata fields, rejecting ambiguous duplicates."""
    result: dict[str, str] = {}
    for key, value in _FIELD_RE.findall(body):
        normalized = key.lower().replace(" ", "_")
        if normalized in result:
            raise PlanProtocolError(f"duplicate {key} field")
        result[normalized] = value.strip()
    return result


def _section(body: str, heading: str) -> str | None:
    """Return one exact level-two Markdown section, rejecting duplicates."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$\n(?P<body>.*?)(?=^## |\Z)",
        re.M | re.S,
    )
    matches = list(pattern.finditer(body))
    if len(matches) > 1:
        raise PlanProtocolError(f"duplicate section: {heading}")
    return matches[0].group("body") if matches else None


def _require_sections(body: str, headings: tuple[str, ...], kind: str) -> None:
    """Reject an executable contract missing or duplicating mandatory sections."""
    missing = [heading for heading in headings if _section(body, heading) is None]
    if missing:
        raise PlanProtocolError(f"{kind} is missing section: {missing[0]}")


def phase_numbers(plan: dict[str, Any]) -> list[int]:
    """Return ordered Phase references from the Plan's Phases section only."""
    body = str(plan.get("body") or "")
    phases = _section(body, "Phases")
    if phases is None:
        raise PlanProtocolError("Plan is missing section: Phases")
    order = [int(value) for value in _PHASE_RE.findall(phases)]
    if not order or len(order) != len(set(order)):
        raise PlanProtocolError("Plan must declare unique ordered phases")
    return order


def _issue_map(issues: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index issues by number and reject duplicate identities."""
    result: dict[int, dict[str, Any]] = {}
    for issue in issues:
        number = int(issue["number"])
        if number in result:
            raise PlanProtocolError(f"duplicate issue #{number}")
        result[number] = issue
    return result


def parse_phase(issue: dict[str, Any], parent: int) -> PhaseState:
    """Parse one Phase issue and validate its parent and execution metadata."""
    number = int(issue["number"])
    body = str(issue.get("body") or "")
    _require_sections(body, _REQUIRED_PHASE_SECTIONS, f"phase #{number}")
    fields = _fields(body)
    parent_refs = _REF_RE.findall(fields.get("parent_plan", ""))
    if parent_refs != [str(parent)]:
        raise PlanProtocolError(f"phase #{number} must declare Parent plan: #{parent}")
    state = fields.get("state", "")
    if state not in _PHASE_STATES:
        raise PlanProtocolError(f"phase #{number} has invalid State")
    issue_state = str(issue.get("state") or "open")
    if issue_state == "closed" and state != "done":
        raise PlanProtocolError(f"closed phase #{number} must have State: done")
    if issue_state not in {"open", "closed"}:
        raise PlanProtocolError(f"phase #{number} has invalid GitHub state")

    blocked_by = fields.get("blocked_by", "")
    blockers = (
        ()
        if blocked_by.lower() == "none"
        else tuple(int(value) for value in _REF_RE.findall(blocked_by))
    )
    if not blocked_by or (blocked_by.lower() != "none" and not blockers):
        raise PlanProtocolError(f"phase #{number} has invalid Blocked by")

    linked = fields.get("linked_pr", "")
    linked_refs = _REF_RE.findall(linked)
    if linked.lower() == "none":
        linked_pr = None
    elif len(linked_refs) == 1:
        linked_pr = int(linked_refs[0])
    else:
        raise PlanProtocolError(f"phase #{number} has invalid Linked PR")
    return PhaseState(number, state, blockers, linked_pr)


def _open_linked_pr(phase: PhaseState, by_number: dict[int, dict[str, Any]]) -> bool:
    """Return whether a Phase's linked PR exists and is still open."""
    if phase.linked_pr is None:
        return False
    linked = by_number.get(phase.linked_pr)
    if linked is None or not linked.get("pull_request"):
        raise PlanProtocolError(
            f"phase #{phase.number} references missing PR #{phase.linked_pr}"
        )
    state = str(linked.get("state") or "")
    if state not in {"open", "closed"}:
        raise PlanProtocolError(f"PR #{phase.linked_pr} has invalid GitHub state")
    return state == "open"


def _dependency_done(
    number: int,
    current_done: set[int],
    by_number: dict[int, dict[str, Any]],
) -> bool:
    """Return whether reconstructed GitHub state proves a blocker complete."""
    if number in current_done:
        return True
    issue = by_number.get(number)
    if issue is None:
        raise PlanProtocolError(f"missing dependency issue #{number}")
    if str(issue.get("state") or "") != "closed":
        return False
    fields = _fields(str(issue.get("body") or ""))
    semantic_state = fields.get("state")
    return semantic_state in {None, "done"}


def next_runnable_phase(plan: dict[str, Any], issues: list[dict[str, Any]]) -> int | None:
    """Return the next runnable Phase number, failing closed on bad metadata.

    Semantic activity and open linked PRs always win over selecting new work.
    Otherwise the first ready Phase in Plan order whose dependencies have
    authoritative completion evidence is selected.
    """
    plan_number = int(plan["number"])
    body = str(plan.get("body") or "")
    fields = _fields(body)
    if fields.get("protocol") != "1":
        raise PlanProtocolError("Plan must declare Protocol: 1")
    state = fields.get("state", "")
    if state not in _PLAN_STATES:
        raise PlanProtocolError("Plan has invalid State")
    if state == "draft":
        return None
    _require_sections(body, _REQUIRED_PLAN_SECTIONS, "Plan")
    if state not in {"ready", "running"}:
        return None

    preconditions = _section(body, "Preconditions")
    assert preconditions is not None
    if re.search(r"^- \[ \] ", preconditions, re.M):
        return None

    order = phase_numbers(plan)
    by_number = _issue_map(issues)
    phases: list[PhaseState] = []
    for number in order:
        issue = by_number.get(number)
        if issue is None:
            raise PlanProtocolError(f"missing phase issue #{number}")
        phases.append(parse_phase(issue, plan_number))

    linked_pr_open = {phase.number: _open_linked_pr(phase, by_number) for phase in phases}
    active = [
        phase
        for phase in phases
        if phase.state in _ACTIVE_PHASE_STATES or linked_pr_open[phase.number]
    ]
    if len(active) > 1:
        raise PlanProtocolError("multiple active phases")
    if active:
        return active[0].number

    done = {phase.number for phase in phases if phase.state == "done"}
    for phase in phases:
        if phase.state == "ready" and all(
            _dependency_done(blocker, done, by_number) for blocker in phase.blockers
        ):
            return phase.number
    return None
