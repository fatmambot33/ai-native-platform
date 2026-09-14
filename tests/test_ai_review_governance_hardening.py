"""Regression tests for trusted AI-review workflow governance."""

from __future__ import annotations

from pathlib import Path

from ai_native import _codeowners_effective_owners, _single_ai_review_workflow_findings

GATE_REF = "0b5ce84c0d6560adffce4b1c32e08ba2a57de7ea"
ACTION = f"fatmambot33/ai-native-platform/actions/codex-review-gate@{GATE_REF}"
WAIT_CONDITION = (
    "(github.event_name == 'pull_request' || "
    "github.event_name == 'pull_request_review' || "
    "github.event_name == 'pull_request_review_thread') && "
    "github.event.pull_request.draft == false"
)
WORKFLOW = f"""name: Codex review governance
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]
  pull_request_target:
    types: [labeled]
  pull_request_review:
    types: [submitted, dismissed]
  pull_request_review_thread:
    types: [resolved, unresolved]
permissions:
  contents: read
concurrency:
  group: codex-review-${{{{ github.event_name }}}}-${{{{ github.event.pull_request.number }}}}
  cancel-in-progress: false
jobs:
  request:
    if: >-
      github.event_name == 'pull_request_target' &&
      github.event.action == 'labeled' &&
      github.event.label.name == 'codex:review' &&
      github.event.pull_request.draft == false
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      issues: write
      pull-requests: read
    steps:
      - uses: {ACTION}
        with:
          token: ${{{{ github.token }}}}
          pr-number: ${{{{ github.event.pull_request.number }}}}
          head-sha: ${{{{ github.event.pull_request.head.sha }}}}
          base-sha: ${{{{ github.event.pull_request.base.sha }}}}
          mode: request
          request-label: codex:review
  codex-review:
    if: {WAIT_CONDITION}
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      issues: read
      pull-requests: read
    steps:
      - uses: {ACTION}
        with:
          token: ${{{{ github.token }}}}
          pr-number: ${{{{ github.event.pull_request.number }}}}
          head-sha: ${{{{ github.event.pull_request.head.sha }}}}
          base-sha: ${{{{ github.event.pull_request.base.sha }}}}
          mode: wait
          request-label: codex:review
"""


def _write_repository(root: Path, workflow: str = WORKFLOW, *, codeowners: bool = True) -> None:
    workflow_path = root / ".github" / "workflows" / "codex-review.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(workflow, encoding="utf-8")
    if codeowners:
        owners = root / ".github" / "CODEOWNERS"
        owners.write_text(
            "/.github/workflows/** @repository-owner\n/.github/CODEOWNERS @repository-owner\n",
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
    workflow = (
        WORKFLOW
        + """  extra-target-job:
    if: github.event_name == 'pull_request_target'
    permissions:
      contents: write
    steps:
      - run: echo unsafe
"""
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any(
        "workflow must contain only request and codex-review jobs" in item.message
        for item in findings
    )


def test_review_gate_requires_review_dismissal_recheck(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_review:\n    types: [submitted, dismissed]\n",
        "",
    )
    _write_repository(tmp_path, workflow)

    findings = _findings(tmp_path)

    assert any("submitted and dismissed" in item.message for item in findings)


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
        '          mode: wait\n          timeout-seconds: "0"\n          poll-seconds: nope\n',
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
        "/codex-review.yml @repository-owner\n/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )

    assert (
        _codeowners_effective_owners(tmp_path, Path(".github/workflows/codex-review.yml")) is None
    )
    findings = _findings(tmp_path)
    assert any("must be covered by .github/CODEOWNERS" in item.message for item in findings)


def test_codeowners_ignores_commented_rules(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "# /.github/workflows/** @repository-owner\n/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )

    assert (
        _codeowners_effective_owners(tmp_path, Path(".github/workflows/codex-review.yml")) is None
    )


def test_codeowners_at_github_size_limit_is_rejected(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text("#" * (3 * 1024 * 1024), encoding="utf-8")

    assert (
        _codeowners_effective_owners(tmp_path, Path(".github/workflows/codex-review.yml")) is None
    )
    assert any("CODEOWNERS" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_extra_request_write_permissions(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "      contents: read\n      issues: write", "      contents: write\n      issues: write"
    )
    _write_repository(tmp_path, workflow)
    assert any("permissions must be exactly" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n",
        "    types: [synchronize, labeled]\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("opened, synchronize, reopened" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_runner(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", "", 1)
    _write_repository(tmp_path, workflow)
    assert any("canonical ubuntu-latest" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_concurrency_override(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    concurrency: global\n", 1
    )
    _write_repository(tmp_path, workflow)
    assert any(
        "must not override workflow concurrency" in item.message for item in _findings(tmp_path)
    )


def test_review_gate_rejects_job_timeout_override(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    timeout-minutes: 1\n", 1
    )
    _write_repository(tmp_path, workflow)
    assert any("must not override timeout-minutes" in item.message for item in _findings(tmp_path))


def test_review_gate_preserves_required_check_name(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  codex-review:\n", "  codex-review:\n    name: Not the required check\n", 1
    )
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


def test_review_gate_requires_base_sha_input(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          base-sha: ${{ github.event.pull_request.base.sha }}\n", "", 1
    )
    _write_repository(tmp_path, workflow)
    assert any("canonical gate step" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n",
        "    types: [opened, synchronize, reopened, ready_for_review, labeled]\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("edited, and labeled" in item.message for item in _findings(tmp_path))


def test_review_gate_restricts_target_to_review_label(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_target:\n    types: [labeled]\n",
        "  pull_request_target:\n    types: [labeled, synchronize]\n",
    )
    _write_repository(tmp_path, workflow)
    assert any(
        "pull_request_target must run only on labeled" in item.message
        for item in _findings(tmp_path)
    )


def test_review_gate_requires_explicit_review_label_condition(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "      github.event.label.name == 'codex:review' &&\n",
        "      github.event.label.name == 'other' &&\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("codex:review labeled events" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_actions_read(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("      actions: read\n", "", 1)
    _write_repository(tmp_path, workflow)
    assert any("permissions must be exactly" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_container(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    container: attacker/image:latest\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("must not declare a container" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_matrix_strategy(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    strategy:\n      matrix:\n        python: ['3.12']\n",
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
        "          mode: wait\n          request-label: codex:review\n",
        "          mode: wait\n          request-label: codex:review\n"
        "          timeout-seconds: '08'\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_explicit_pr_activity_types(tmp_path: Path) -> None:
    full_types = (
        "  pull_request:\n"
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
    )
    workflow = WORKFLOW.replace(full_types, "  pull_request:\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("opened, synchronize, reopened" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_services(tmp_path: Path) -> None:
    services = (
        "    runs-on: ubuntu-latest\n"
        "    services:\n"
        "      attacker:\n"
        "        image: attacker/image:latest\n"
    )
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", services, 1)
    _write_repository(tmp_path, workflow)
    assert any("must not declare services" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_symlinked_workflow(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "codex-review.yml"
    target = tmp_path / "trusted-looking.yml"
    target.write_text(WORKFLOW, encoding="utf-8")
    workflow.unlink()
    workflow.symlink_to(target)
    assert any("regular file, not a symlink" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_submitted_review_activity(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("types: [submitted, dismissed]", "types: [dismissed]", 1)
    _write_repository(tmp_path, workflow)
    assert any("submitted and dismissed" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_review_thread_revalidation(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_review_thread:\n    types: [resolved, unresolved]\n", "", 1
    )
    _write_repository(tmp_path, workflow)
    assert any("resolved and unresolved" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_ambiguous_on_keys(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("on:\n", '"on":\n', 1) + "\non:\n  push:\n"
    _write_repository(tmp_path, workflow)
    assert any(
        "exactly one literal top-level on key" in item.message
        for item in _findings(tmp_path)
    )




def test_review_gate_rejects_indirect_ownerless_workflow_override(tmp_path: Path) -> None:
    """Reject broad basename globs that can override future workflow ownership."""
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @repository-owner\n"
        "**/release-*.yml\n"
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("namespace rule" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_huge_timing_without_conversion_error(tmp_path: Path) -> None:
    """Reject huge decimal timing strings without calling int on them first."""
    huge = "9" * 5000
    workflow = WORKFLOW.replace(
        "          mode: wait\n          request-label: codex:review\n",
        "          mode: wait\n          request-label: codex:review\n"
        f"          timeout-seconds: '{huge}'\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_timing_above_runtime_bound(tmp_path: Path) -> None:
    """Keep timing overrides inside the supported Bash arithmetic bound."""
    workflow = WORKFLOW.replace(
        "          mode: wait\n          request-label: codex:review\n",
        "          mode: wait\n          request-label: codex:review\n"
        "          timeout-seconds: '2147483648'\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_workflow_bash_env(tmp_path: Path) -> None:
    """Reject workflow-level BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "permissions:\n  contents: read\n",
        "env:\n  BASH_ENV: /tmp/pwn\npermissions:\n  contents: read\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("trusted gate" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_bash_env(tmp_path: Path) -> None:
    """Reject job-level BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    env:\n      BASH_ENV: /tmp/pwn\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("trusted gate" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_step_bash_env(tmp_path: Path) -> None:
    """Reject gate-step BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "      - uses: ",
        "      - env:\n          BASH_ENV: /tmp/pwn\n        uses: ",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("canonical gate step" in item.message for item in _findings(tmp_path))


def test_review_gate_namespace_rule_must_remain_effective(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @repository-owner\n"
        "/.github/**\n"
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("namespace rule" in item.message for item in _findings(tmp_path))
