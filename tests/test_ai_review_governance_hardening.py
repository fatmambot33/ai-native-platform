"""Regression tests for trusted AI-review workflow governance."""

from __future__ import annotations

from pathlib import Path

from ai_native import _codeowners_effective_owners, _single_ai_review_workflow_findings

GATE_REF = "cd1f286222a286508c962288671c1f6c97b52d95"
ACTION = f"fatmambot33/ai-native-platform/actions/codex-review-gate@{GATE_REF}"
WORKFLOW = f"""name: Codex review governance
on:
  pull_request:
  pull_request_target:
  pull_request_review:
    types: [dismissed]
permissions:
  contents: read
concurrency:
  group: codex-review-${{{{ github.event_name }}}}-${{{{ github.event.pull_request.number }}}}
  cancel-in-progress: true
jobs:
  request:
    if: github.event_name == 'pull_request_target'
    permissions:
      contents: read
      issues: write
      pull-requests: read
    steps:
      - uses: {ACTION}
        with:
          token: ${{{{ github.token }}}}
          pr-number: ${{{{ github.event.pull_request.number }}}}
          head-sha: ${{{{ github.event.pull_request.head.sha }}}}
          mode: request
  codex-review:
    if: (github.event_name == 'pull_request' || github.event_name == 'pull_request_review')
    permissions:
      contents: read
      issues: read
      pull-requests: read
    steps:
      - uses: {ACTION}
        with:
          token: ${{{{ github.token }}}}
          pr-number: ${{{{ github.event.pull_request.number }}}}
          head-sha: ${{{{ github.event.pull_request.head.sha }}}}
          mode: wait
"""


def _write_repository(root: Path, workflow: str = WORKFLOW, *, codeowners: bool = True) -> None:
    workflow_path = root / ".github" / "workflows" / "codex-review.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(workflow, encoding="utf-8")
    if codeowners:
        owners = root / ".github" / "CODEOWNERS"
        owners.write_text(
            "/.github/workflows/** @repository-owner\n"
            "/.github/CODEOWNERS @repository-owner\n",
            encoding="utf-8",
        )


def _findings(root: Path) -> list:
    return _single_ai_review_workflow_findings(".github/workflows/codex-review.yml", root)


def test_trusted_review_workflow_baseline_passes(tmp_path: Path) -> None:
    _write_repository(tmp_path)

    assert _findings(tmp_path) == []


def test_review_gate_rejects_needs_dependency(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  codex-review:\n    if:",
        "  codex-review:\n    needs: bypass\n    if:",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("must not declare needs dependencies" in item.message for item in findings)


def test_review_gate_rejects_job_level_continue_on_error(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  codex-review:\n    if:",
        "  codex-review:\n    continue-on-error: true\n    if:",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("must not suppress job failures" in item.message for item in findings)


def test_review_gate_rejects_additional_jobs(tmp_path: Path) -> None:
    workflow = WORKFLOW + """  extra-target-job:
    if: github.event_name == 'pull_request_target'
    permissions:
      contents: write
    steps:
      - run: echo unsafe
"""
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any(
        "workflow must contain only request and codex-review jobs" in item.message
        for item in findings
    )


def test_review_gate_requires_review_dismissal_recheck(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_review:\n    types: [dismissed]\n",
        "",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("pull_request_review must run on dismissed" in item.message for item in findings)


def test_review_gate_requires_evaluated_concurrency_event_expression(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}",
        "codex-review-github.event_name-${{ github.event.pull_request.number }}",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("canonical evaluated concurrency group" in item.message for item in findings)


def test_review_gate_requires_evaluated_concurrency_pr_expression(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}",
        "codex-review-${{ github.event_name }}-github.event.pull_request.number",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("canonical evaluated concurrency group" in item.message for item in findings)


def test_review_gate_rejects_invalid_optional_timing_inputs(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          mode: wait\n",
        "          mode: wait\n          timeout-seconds: \"0\"\n          poll-seconds: nope\n",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("positive timing overrides" in item.message for item in findings)


def test_review_gate_requires_codeowners_coverage(tmp_path: Path) -> None:
    _write_repository(tmp_path, codeowners=False)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    if codeowners.exists():
        codeowners.unlink()

    findings = _findings(tmp_path)

    assert any("must be covered by .github/CODEOWNERS" in item.message for item in findings)


def test_review_gate_requires_codeowners_self_ownership(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text("/.github/workflows/** @repository-owner\n", encoding="utf-8")

    findings = _findings(tmp_path)

    assert any("CODEOWNERS must protect itself" in item.message for item in findings)


def test_review_gate_rejects_ownerless_last_codeowners_override(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n"
        "/.github/workflows/codex-review.yml\n",
        encoding="utf-8",
    )

    findings = _findings(tmp_path)

    assert any("must be covered by .github/CODEOWNERS" in item.message for item in findings)


def test_codeowners_root_anchor_does_not_match_nested_basename(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )

    assert _codeowners_effective_owners(
        tmp_path, Path(".github/workflows/codex-review.yml")
    ) is None
    findings = _findings(tmp_path)
    assert any(
        "must be covered by .github/CODEOWNERS" in item.message for item in findings
    )


def test_codeowners_ignores_commented_rules(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "# /.github/workflows/** @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )

    assert _codeowners_effective_owners(
        tmp_path, Path(".github/workflows/codex-review.yml")
    ) is None
