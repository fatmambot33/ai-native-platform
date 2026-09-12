"""One-shot patcher for remaining Codex governance findings."""

from __future__ import annotations

from pathlib import Path

ROOT = Path.cwd()
OLD_REF = "6f365e9bfba6a44bc208e8acd778809fd7eb1c49"
NEW_REF = "db5cb7440dac086137afc93e32a69a6230556f57"


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker not in text:
        target.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def patch_validator() -> None:
    path = "ai_native.py"
    replace(path, OLD_REF, NEW_REF)
    replace(
        path,
        '    required = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}\n',
        '    required = {"opened", "synchronize", "reopened", "ready_for_review", "edited", "labeled"}\n',
    )

    marker = "\ndef _event_runs_on_review_dismissal(workflow: Mapping[Any, Any]) -> bool:\n"
    helper = '''
def _event_runs_only_on_label(workflow: Mapping[Any, Any], event_name: str) -> bool:
    """Return whether an event is restricted to label changes only."""
    events = _workflow_events_value(workflow)
    if not isinstance(events, Mapping) or event_name not in events:
        return False
    config = events[event_name]
    if not isinstance(config, Mapping):
        return False
    types = config.get("types")
    if isinstance(types, str):
        return types == "labeled"
    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):
        return {str(item) for item in types} == {"labeled"}
    return False

'''
    replace(path, marker, "\n" + helper + marker.lstrip("\n"))

    marker = "\ndef _uses_review_wait_events(job: Mapping[str, Any]) -> bool:\n"
    helper = '''
def _uses_labeled_review_request(job: Mapping[str, Any]) -> bool:
    """Return whether request execution is bound to the one-shot review label."""
    condition = _normalize_condition(job.get("if"))
    event_guard = (
        "github.event_name == 'pull_request_target' && github.event.action == 'labeled' "
        "&& github.event.label.name == 'codex:review'"
    )
    draft_guard = f"{event_guard} && github.event.pull_request.draft == false"
    return condition in {event_guard, draft_guard}

'''
    replace(path, marker, "\n" + helper + marker.lstrip("\n"))

    replace(
        path,
        '''def _positive_integer_input(value: Any) -> bool:
    """Return whether an action input represents a positive integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str) and value.isdigit():
        return int(value) > 0
    return False
''',
        '''def _positive_integer_input(value: Any) -> bool:
    """Return whether an action input is a Bash-safe positive decimal integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        return re.fullmatch(r"[1-9][0-9]*", value) is not None
    return False
''',
    )

    replace(
        path,
        '        "mode": mode,\n    }\n',
        '        "mode": mode,\n        "request-label": "codex:review",\n    }\n',
    )

    replace(
        path,
        '''    events = _workflow_events(workflow)
    for event_name in ("pull_request", "pull_request_target"):
        if event_name not in events:
            failures.append(f"missing {event_name} event")
        elif not _event_runs_on_required_pr_activities(workflow, event_name):
            failures.append(
                f"{event_name} must run on opened, synchronize, reopened, ready_for_review, and edited"
            )
''',
        '''    events = _workflow_events(workflow)
    if "pull_request" not in events:
        failures.append("missing pull_request event")
    elif not _event_runs_on_required_pr_activities(workflow, "pull_request"):
        failures.append(
            "pull_request must run on opened, synchronize, reopened, "
            "ready_for_review, edited, and labeled"
        )
    if "pull_request_target" not in events:
        failures.append("missing pull_request_target event")
    elif not _event_runs_only_on_label(workflow, "pull_request_target"):
        failures.append("pull_request_target must run only on labeled events")
''',
    )

    replace(
        path,
        '    if not _uses_event(request, "pull_request_target"):\n'
        '        failures.append("request job condition must canonically bind pull_request_target")\n',
        '    if not _uses_labeled_review_request(request):\n'
        '        failures.append(\n'
        '            "request job condition must bind only codex:review labeled events"\n'
        '        )\n',
    )

    replace(
        path,
        '''        runner = job.get("runs-on")
        if not isinstance(runner, str) or not runner.strip():
            failures.append(f"{label} job must declare a nonempty runs-on runner")
        if "timeout-minutes" in job:
            failures.append(f"{label} job must not override timeout-minutes")
        if "concurrency" in job:
            failures.append(f"{label} job must not override workflow concurrency")
''',
        '''        runner = job.get("runs-on")
        if runner != "ubuntu-latest":
            failures.append(f"{label} job must run on canonical ubuntu-latest")
        if "container" in job:
            failures.append(f"{label} job must not declare a container")
        if "strategy" in job:
            failures.append(f"{label} job must not declare a strategy or matrix")
        if "timeout-minutes" in job:
            failures.append(f"{label} job must not override timeout-minutes")
        if "concurrency" in job:
            failures.append(f"{label} job must not override workflow concurrency")
''',
    )

    replace(
        path,
        '''    expected_request_permissions = {
        "contents": "read",
        "issues": "write",
        "pull-requests": "read",
    }
''',
        '''    expected_request_permissions = {
        "actions": "read",
        "contents": "read",
        "issues": "write",
        "pull-requests": "read",
    }
''',
    )
    replace(
        path,
        '            "request job permissions must be exactly contents: read, issues: write, "\n'
        '            "and pull-requests: read"\n',
        '            "request job permissions must be exactly actions/contents: read, "\n'
        '            "issues: write, and pull-requests: read"\n',
    )
    replace(
        path,
        '''    expected_wait_permissions = {
        "contents": "read",
        "issues": "read",
        "pull-requests": "read",
    }
''',
        '''    expected_wait_permissions = {
        "actions": "read",
        "contents": "read",
        "issues": "read",
        "pull-requests": "read",
    }
''',
    )
    replace(
        path,
        '            "codex-review job permissions must be exactly contents/issues/pull-requests: read"\n',
        '            "codex-review job permissions must be exactly "\n'
        '            "actions/contents/issues/pull-requests: read"\n',
    )


def patch_hardening_tests() -> None:
    path = "tests/test_ai_review_governance_hardening.py"
    replace(path, OLD_REF, NEW_REF)
    replace(
        path,
        "on:\n  pull_request:\n  pull_request_target:\n  pull_request_review:\n",
        "on:\n  pull_request:\n"
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
        "  pull_request_target:\n    types: [labeled]\n  pull_request_review:\n",
    )
    replace(
        path,
        "    if: github.event_name == 'pull_request_target'\n",
        "    if: >-\n"
        "      github.event_name == 'pull_request_target' &&\n"
        "      github.event.action == 'labeled' &&\n"
        "      github.event.label.name == 'codex:review'\n",
    )
    replace(path, "    permissions:\n      contents: read\n      issues: write\n", "    permissions:\n      actions: read\n      contents: read\n      issues: write\n", 1)
    replace(path, "    permissions:\n      contents: read\n      issues: read\n", "    permissions:\n      actions: read\n      contents: read\n      issues: read\n", 1)
    replace(path, "          mode: request\n", "          mode: request\n          request-label: codex:review\n", 1)
    replace(path, "          mode: wait\n", "          mode: wait\n          request-label: codex:review\n", 1)

    replace(
        path,
        '''def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request:\\n", "  pull_request:\\n    types: [synchronize]\\n", 1
    )
    _write_repository(tmp_path, workflow)
    assert any(
        "opened, synchronize, reopened, ready_for_review, and edited" in item.message
        for item in _findings(tmp_path)
    )
''',
        '''def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\\n",
        "    types: [synchronize, labeled]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any(
        "opened, synchronize, reopened" in item.message for item in _findings(tmp_path)
    )
''',
    )
    replace(
        path,
        '''def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request:\\n",
        "  pull_request:\\n    types: [opened, synchronize, reopened, ready_for_review]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("ready_for_review, and edited" in item.message for item in _findings(tmp_path))
''',
        '''def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\\n",
        "    types: [opened, synchronize, reopened, ready_for_review, labeled]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("edited, and labeled" in item.message for item in _findings(tmp_path))
''',
    )

    append_once(
        path,
        "test_review_gate_restricts_target_to_review_label",
        '''
def test_review_gate_restricts_target_to_review_label(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_target:\\n    types: [labeled]\\n",
        "  pull_request_target:\\n    types: [labeled, synchronize]\\n",
    )
    _write_repository(tmp_path, workflow)
    assert any(
        "pull_request_target must run only on labeled" in item.message
        for item in _findings(tmp_path)
    )


def test_review_gate_requires_explicit_review_label_condition(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "      github.event.label.name == 'codex:review'\\n",
        "      github.event.label.name == 'other'\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("codex:review labeled events" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_actions_read(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("      actions: read\\n", "", 1)
    _write_repository(tmp_path, workflow)
    assert any("permissions must be exactly" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_container(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\\n",
        "    runs-on: ubuntu-latest\\n    container: attacker/image:latest\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("must not declare a container" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_matrix_strategy(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\\n",
        "    runs-on: ubuntu-latest\\n    strategy:\\n      matrix:\\n        python: ['3.12']\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("must not declare a strategy" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_canonical_runner(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("runs-on: ubuntu-latest", "runs-on: self-hosted", 1)
    _write_repository(tmp_path, workflow)
    assert any("canonical ubuntu-latest" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_bash_unsafe_timing_strings(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          mode: wait\\n          request-label: codex:review\\n",
        "          mode: wait\\n          request-label: codex:review\\n"
        "          timeout-seconds: '08'\\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))
''',
    )


def patch_validation_tests() -> None:
    path = "tests/test_validation.py"
    replace(path, OLD_REF, NEW_REF)
    replace(
        path,
        "on:\n  pull_request:\n  pull_request_target:\n  pull_request_review:\n",
        "on:\n  pull_request:\n"
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
        "  pull_request_target:\n    types: [labeled]\n  pull_request_review:\n",
        1,
    )
    replace(
        path,
        "    if: github.event_name == 'pull_request_target'\n",
        "    if: >-\n"
        "      github.event_name == 'pull_request_target' &&\n"
        "      github.event.action == 'labeled' &&\n"
        "      github.event.label.name == 'codex:review'\n",
        1,
    )
    replace(path, "    permissions:\n      contents: read\n      issues: write\n", "    permissions:\n      actions: read\n      contents: read\n      issues: write\n", 1)
    replace(path, "    permissions:\n      contents: read\n      issues: read\n", "    permissions:\n      actions: read\n      contents: read\n      issues: read\n", 1)
    replace(path, "          mode: request\n", "          mode: request\n          request-label: codex:review\n", 1)
    replace(path, "          mode: wait\n", "          mode: wait\n          request-label: codex:review\n", 1)


def patch_gate_tests() -> None:
    path = "tests/test_codex_review_gate.py"
    append_once(
        path,
        "test_explicit_label_can_replace_a_dismissed_review",
        '''
def test_explicit_label_can_replace_a_dismissed_review() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    dismissed = _function_body(script, "has_dismissed_matching_review")

    assert "DISMISSED" in dismissed
    assert "has_dismissed_matching_review" in request
    assert "authorizes one replacement review" in request


def test_review_requests_are_quota_aware() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    failure = _function_body(script, "codex_failure_after")

    assert 'REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"' in script
    assert "still pending; preserving quota" in request
    assert "reached your Codex usage limits for code reviews" in failure
    assert "No automatic retry will be attempted" in failure
''',
    )


def patch_governance() -> None:
    path = ".github/CODEOWNERS"
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if not text.startswith("* @fatmambot33\n"):
        target.write_text("* @fatmambot33\n" + text, encoding="utf-8")

    replace(
        "standard/AI_NATIVE_PLATFORM.yaml",
        "  - migration_notes_for_breaking_changes\n  - ai_review_current_head\n  - review_threads_resolved\n",
        "  - migration_notes_for_breaking_changes\n  - branch_up_to_date\n",
    )

    append_once(
        "docs/AI_REVIEW_GOVERNANCE.md",
        "## Quota-aware review lifecycle",
        '''
## Quota-aware review lifecycle

Codex review is asynchronous and quota-limited. Deterministic CI, linting,
tests, conformance, and security checks run during normal iteration. New
commits invalidate stale Codex evidence but do not automatically spend another
review.

For repositories opting into AI-review governance, branch protection MUST
require the pull request branch to be up to date with its protected base before
merge (GitHub strict required-status-check policy or an equivalent rule). This
prevents a clean review for an older base revision from remaining mergeable
after the base advances. The reference repository enforces this rule.

When the exact current HEAD/base pair is green and merge-ready, apply the
one-shot `codex:review` label. The privileged `pull_request_target` path runs
only for that label. Both request and wait jobs require `actions: read` so
server-verified workflow-run provenance also works in private repositories.
The request is deduplicated while pending, but a dismissed matching review may
be deliberately replaced by applying the label again.

If Codex reports code-review quota exhaustion or a terminal request failure,
the gate fails closed and never retries automatically. Re-apply the label only
after capacity returns or the failure is understood. The merge invariant is
unchanged: exact current HEAD/base Codex evidence and zero unresolved
Codex-authored review threads.
''',
    )

    append_once(
        "AGENTS.md",
        "Treat Codex code review as asynchronous and quota-limited",
        '''
- Treat Codex code review as asynchronous and quota-limited: batch fixes,
  rely on deterministic checks during iteration, request a fresh review only
  for a merge-ready exact HEAD/base checkpoint, and never auto-retry a failed
  or quota-exhausted review.
''',
    )


def main() -> None:
    patch_validator()
    patch_hardening_tests()
    patch_validation_tests()
    patch_gate_tests()
    patch_governance()
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
