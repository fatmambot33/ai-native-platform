"""Apply the reviewed AI-governance hardening to the alignment branch."""

from __future__ import annotations

from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace one exact fragment or fail loudly."""
    if old not in text:
        raise SystemExit(f"missing replacement target: {label}")
    return text.replace(old, new, 1)


def regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    """Replace one regex fragment or fail loudly."""
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"missing regex replacement target: {label} ({count})")
    return updated


path = Path("ai_native.py")
text = path.read_text(encoding="utf-8")

text = regex_once(
    text,
    r"def _event_runs_on_synchronize\(.*?(?=\ndef _event_runs_on_review_dismissal)",
    '''def _event_runs_on_required_pr_activities(
    workflow: Mapping[Any, Any], event_name: str
) -> bool:
    """Return whether a PR event covers every current-HEAD transition."""
    required = {"opened", "synchronize", "reopened", "ready_for_review"}
    events = _workflow_events_value(workflow)
    if isinstance(events, str):
        return events == event_name
    if isinstance(events, Sequence) and not isinstance(events, (str, bytes, Mapping)):
        return event_name in {str(item) for item in events}
    if not isinstance(events, Mapping) or event_name not in events:
        return False
    config = events[event_name]
    if config is None:
        return True
    if not isinstance(config, Mapping):
        return False
    types = config.get("types")
    if types is None:
        return True
    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):
        return required <= {str(item) for item in types}
    return False


''',
    "PR event coverage helper",
)

text = regex_once(
    text,
    r"def _codeowners_covers_path\(.*?(?=\ndef _single_ai_review_workflow_findings)",
    '''def _valid_codeowner(owner: str) -> bool:
    """Return whether a CODEOWNERS owner token has a supported identity shape."""
    handle = re.fullmatch(
        r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)?",
        owner,
    )
    email = re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", owner)
    return handle is not None or email is not None


def _codeowners_covers_path(root: Path, relative: Path) -> bool:
    """Return whether the effective CODEOWNERS rule assigns valid owners."""
    effective_owners = _codeowners_effective_owners(root, relative)
    return bool(effective_owners) and all(
        _valid_codeowner(owner) for owner in effective_owners
    )


''',
    "CODEOWNERS identity validation",
)

text = replace_once(
    text,
    "or len(relative.parts) < 3\n",
    "or len(relative.parts) != 3\n",
    "top-level workflow evidence",
)
text = replace_once(
    text,
    '''        elif not _event_runs_on_synchronize(workflow, event_name):
            failures.append(f"{event_name} must run on synchronize")''',
    '''        elif not _event_runs_on_required_pr_activities(workflow, event_name):
            failures.append(
                f"{event_name} must run on opened, synchronize, reopened, and ready_for_review"
            )''',
    "required PR activity validation",
)

text = replace_once(
    text,
    '''    if request.get("continue-on-error") not in (None, False):
        failures.append("request job must not suppress job failures")
    if wait.get("continue-on-error") not in (None, False):
        failures.append("codex-review job must not suppress job failures")

    if not _uses_event(request, "pull_request_target"):
''',
    '''    if request.get("continue-on-error") not in (None, False):
        failures.append("request job must not suppress job failures")
    if wait.get("continue-on-error") not in (None, False):
        failures.append("codex-review job must not suppress job failures")
    for label, job in (("request", request), ("codex-review", wait)):
        runner = job.get("runs-on")
        if not isinstance(runner, str) or not runner.strip():
            failures.append(f"{label} job must declare a nonempty runs-on runner")
        if "timeout-minutes" in job:
            failures.append(f"{label} job must not override timeout-minutes")
        if "concurrency" in job:
            failures.append(f"{label} job must not override workflow concurrency")
    if wait.get("name") not in (None, "codex-review"):
        failures.append("codex-review job name must remain codex-review")

    if not _uses_event(request, "pull_request_target"):
''',
    "job execution constraints",
)

text = regex_once(
    text,
    r"    request_permissions = _job_permissions\(request\)\n.*?(?=\n    concurrency = workflow.get)",
    '''    request_permissions = _job_permissions(request)
    expected_request_permissions = {
        "contents": "read",
        "issues": "write",
        "pull-requests": "read",
    }
    if dict(request_permissions) != expected_request_permissions:
        failures.append(
            "request job permissions must be exactly contents: read, issues: write, "
            "and pull-requests: read"
        )
    wait_permissions = _job_permissions(wait)
    expected_wait_permissions = {
        "contents": "read",
        "issues": "read",
        "pull-requests": "read",
    }
    if dict(wait_permissions) != expected_wait_permissions:
        failures.append(
            "codex-review job permissions must be exactly contents/issues/pull-requests: read"
        )
''',
    "least-privilege permissions",
)

text = replace_once(
    text,
    '''    if not _codeowners_covers_path(root, relative):
        failures.append("declared AI review workflow must be covered by .github/CODEOWNERS")
    if not _codeowners_covers_path(root, Path(".github/CODEOWNERS")):
        failures.append(".github/CODEOWNERS must protect itself with an effective owner rule")
''',
    '''    if not _codeowners_covers_path(root, relative):
        failures.append("declared AI review workflow must be covered by .github/CODEOWNERS")
    if not _codeowners_covers_path(
        root, Path(".github/workflows/__ai_native_required_check_probe__.yml")
    ):
        failures.append("the entire .github/workflows namespace must be CODEOWNERS-protected")
    if not _codeowners_covers_path(root, Path(".github/CODEOWNERS")):
        failures.append(".github/CODEOWNERS must protect itself with an effective owner rule")
''',
    "workflow namespace ownership",
)
path.write_text(text, encoding="utf-8")

path = Path("validator/validate_standard.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '        "actions/codex-review-gate/action.yml",\n',
    '        "actions/codex-review-gate/action.yml",\n'
    '        "actions/codex-review-gate/codex-review-gate.sh",\n'
    '        ".github/workflows/__ai_native_required_check_probe__.yml",\n',
    "canonical governed paths",
)
path.write_text(text, encoding="utf-8")

path = Path("templates/AI_NATIVE_PLATFORM.yaml")
text = path.read_text(encoding="utf-8").replace(
    "# AI review governance is unreleased and intentionally omitted from the v0.2 starter.",
    "# AI review governance is opt-in and intentionally omitted from the v0.3 starter.",
)
path.write_text(text, encoding="utf-8")

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "## Unreleased\n",
    """## Unreleased

### Added

- Add opt-in `evidence.paths.ai_review_workflow` governance evidence with structural validation of trusted current-HEAD Codex review workflows.
- Add a reusable Codex review gate that binds automated clean-reaction requests to the exact PR HEAD through server-verified GitHub Actions request-run provenance.

### Security

- Require request jobs to use least-privilege permissions, keep wait jobs read-only, preserve the `codex-review` check name, and reject job-level concurrency/timeouts that can bypass or destabilize the gate.
- Require full pull-request activity coverage, direct `.github/workflows` placement, valid CODEOWNERS identities, workflow-namespace ownership, executable runner declarations, and ownership of the reusable gate implementation.
- Keep one-time bootstrap evidence limited to unedited OWNER/MEMBER/COLLABORATOR requests for repositories that have not yet landed the protected request workflow.

### Migration

- Consumers opting into `ai_review_workflow` must pin the gate action to an immutable trusted framework commit, protect `/.github/workflows/**` and `/.github/CODEOWNERS`, require the `codex-review` check, enable code-owner review with stale approvals dismissed on new pushes, and keep conversation resolution enabled.

""",
    "changelog governance notes",
)
path.write_text(text, encoding="utf-8")

path = Path("RELEASE_NOTES.md")
text = path.read_text(encoding="utf-8")
addition = """

## AI-review governance opt-in

Repositories may opt into `evidence.paths.ai_review_workflow` to make current-HEAD Codex review part of merge governance. The declared workflow must pin the reusable gate to an immutable trusted framework commit, use a protected `pull_request_target` request path plus a read-only `pull_request`/review-dismissal wait path, and preserve the required `codex-review` check name.

Adoption is a one-time bootstrap: land the governed workflow and CODEOWNERS rules, then require `codex-review`, enable **Require review from Code Owners**, enable dismissal of stale approvals on new pushes (or equivalent latest-push approval protection), and keep conversation resolution required. Automated clean-reaction requests are bound to server-verified GitHub Actions run provenance for the exact PR and HEAD; the privileged maintainer bootstrap fallback exists only before the trusted request workflow is present on the default branch.
"""
if "## AI-review governance opt-in" not in text:
    text += addition
path.write_text(text, encoding="utf-8")

path = Path("docs/AI_REVIEW_GOVERNANCE.md")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''A clean reaction normally comes from the HEAD-specific request created by the trusted request job. The request must remain unedited (`created_at == updated_at`), must contain the full current-HEAD marker, and must have been created no earlier than the server-supplied activation timestamp for that exact PR HEAD.

The one-time bootstrap path also accepts an unedited request from an `OWNER`, `MEMBER`, or `COLLABORATOR` when the new trusted `pull_request_target` workflow is not yet present on the default branch. The first line must be the exact `@codex review` command, the comment must contain the full current-HEAD marker, and its creation time must be at or after the current HEAD activation timestamp. Request mode never creates or relies on this maintainer fallback; it exists only so the bootstrap wait path can validate genuine Codex clean-reaction evidence without rebinding an older reaction.
''',
    '''A clean reaction normally comes from the HEAD-specific request created by the trusted request job. The request must remain unedited (`created_at == updated_at`), contain the full current-HEAD marker, and carry the request workflow run ID. The wait gate verifies that run through GitHub's server API: it must be the same workflow ID and workflow path, must have been triggered by `pull_request_target`, and GitHub must associate it with the exact pull request number and HEAD SHA before the request reaction is trusted. This avoids using mutable pull-request timestamps or contributor-controlled commit dates as freshness evidence.

The one-time bootstrap path also accepts an unedited request from an `OWNER`, `MEMBER`, or `COLLABORATOR` when the new trusted `pull_request_target` workflow is not yet present on the default branch. The first line must be the exact `@codex review` command and the comment must contain the full current-HEAD marker. This is an explicitly privileged bootstrap exception rather than automated run provenance; request mode never creates or relies on it.
''',
    "governance provenance docs",
)
text = text.replace(
    "positive numeric timing overrides when supplied, no writable status/check API, and effective CODEOWNERS protection for both the workflow and `.github/CODEOWNERS` itself.",
    "positive numeric timing overrides when supplied, no job-level timeout/concurrency overrides, exact least-privilege permissions, executable runners, a stable `codex-review` check name, no writable status/check API, and effective CODEOWNERS protection for the full workflow namespace plus `.github/CODEOWNERS` itself.",
)
path.write_text(text, encoding="utf-8")

path = Path("tests/test_ai_review_governance_hardening.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "  request:\n    if: github.event_name == 'pull_request_target'\n",
    "  request:\n    if: github.event_name == 'pull_request_target'\n    runs-on: ubuntu-latest\n",
    1,
)
text = text.replace(
    "  codex-review:\n    if: (github.event_name == 'pull_request' || github.event_name == 'pull_request_review')\n",
    "  codex-review:\n    if: (github.event_name == 'pull_request' || github.event_name == 'pull_request_review')\n    runs-on: ubuntu-latest\n",
    1,
)
addition = r'''


def test_review_gate_rejects_extra_request_write_permissions(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("      contents: read\n      issues: write", "      contents: write\n      issues: write")
    _write_repository(tmp_path, workflow)
    assert any("permissions must be exactly" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("  pull_request:\n", "  pull_request:\n    types: [synchronize]\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("opened, synchronize, reopened, and ready_for_review" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_runner(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", "", 1)
    _write_repository(tmp_path, workflow)
    assert any("must declare a nonempty runs-on runner" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_concurrency_override(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    concurrency: global\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("must not override workflow concurrency" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_timeout_override(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    timeout-minutes: 1\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("must not override timeout-minutes" in item.message for item in _findings(tmp_path))


def test_review_gate_preserves_required_check_name(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("  codex-review:\n", "  codex-review:\n    name: Not the required check\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("job name must remain codex-review" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_top_level_workflow_file(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    nested = tmp_path / ".github" / "workflows" / "archive" / "codex-review.yml"
    nested.parent.mkdir(parents=True)
    nested.write_text(WORKFLOW, encoding="utf-8")
    findings = _single_ai_review_workflow_findings(
        ".github/workflows/archive/codex-review.yml", tmp_path
    )
    assert any("must point to a .github/workflows YAML file" in item.message for item in findings)


def test_review_gate_rejects_invalid_codeowner_identity(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    owners = tmp_path / ".github" / "CODEOWNERS"
    owners.write_text("/.github/workflows/** @\n/.github/CODEOWNERS @\n", encoding="utf-8")
    assert any("CODEOWNERS" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_workflow_namespace_ownership(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    owners = tmp_path / ".github" / "CODEOWNERS"
    owners.write_text(
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("entire .github/workflows namespace" in item.message for item in _findings(tmp_path))
'''
if "test_review_gate_rejects_extra_request_write_permissions" not in text:
    text += addition
path.write_text(text, encoding="utf-8")

path = Path("tests/test_codex_review_gate.py")
text = path.read_text(encoding="utf-8")
text = regex_once(
    text,
    r"def test_clean_reaction_request_must_postdate_current_head_activation\(\) -> None:\n.*?(?=\ndef test_thread_pagination_errors_fail_closed)",
    '''def test_clean_reaction_request_uses_trusted_run_provenance() -> None:
    script = GATE.read_text(encoding="utf-8")
    trusted = _function_body(script, "trusted_request_run")
    bot = _function_body(script, "find_bot_trigger_comment")

    assert ".pull_request.updated_at" not in script
    assert '.event == "pull_request_target"' in trusted
    assert ".workflow_id" in trusted
    assert ".path == $workflow_path" in trusted
    assert ".pull_requests[]?" in trusted
    assert '(.head.sha // "") == $head' in trusted
    assert "ai-native-codex-review-run" in bot


def test_request_comment_records_request_run_id() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert "RUN_MARKER" in script
    assert '"$RUN_MARKER"' in request


''',
    "gate provenance regression test",
)
path.write_text(text, encoding="utf-8")
