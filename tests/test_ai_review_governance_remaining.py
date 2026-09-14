"""Regression coverage for the final AI-review governance findings."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_native import (
    _ai_review_workflow_findings,
    _single_ai_review_workflow_findings,
    contract_findings,
    load_mapping,
    template_path,
)

GATE_REF = "2c0e08d1ef9315c8b3f5693b4b51796d12cc02ff"
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
      github.event.label.name == 'codex:review'
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


def _write_repository(root: Path, workflow: str = WORKFLOW) -> None:
    workflow_path = root / ".github" / "workflows" / "codex-review.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(workflow, encoding="utf-8")
    (root / ".github" / "CODEOWNERS").write_text(
        "/.github/workflows/** @repository-owner\n/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )


def _findings(root: Path) -> list:
    return _single_ai_review_workflow_findings(".github/workflows/codex-review.yml", root)


@pytest.mark.parametrize(
    ("event", "key"),
    [
        ("pull_request", "branches"),
        ("pull_request", "branches-ignore"),
        ("pull_request", "paths"),
        ("pull_request", "paths-ignore"),
        ("pull_request_target", "branches"),
        ("pull_request_target", "branches-ignore"),
        ("pull_request_target", "paths"),
        ("pull_request_target", "paths-ignore"),
    ],
)
def test_review_gate_rejects_pr_filters(tmp_path: Path, event: str, key: str) -> None:
    needle = (
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
        if event == "pull_request"
        else "    types: [labeled]\n"
    )
    workflow = WORKFLOW.replace(needle, needle + f"    {key}: [main]\n", 1)
    _write_repository(tmp_path, workflow)

    assert _findings(tmp_path)


@pytest.mark.parametrize(
    "key",
    [
        "GH_HOST",
        "GH_TOKEN",
        "GH_ENTERPRISE_TOKEN",
        "GH_CONFIG_DIR",
        "GITHUB_TOKEN",
        "GITHUB_ENTERPRISE_TOKEN",
    ],
)
def test_review_gate_rejects_workflow_cli_env(tmp_path: Path, key: str) -> None:
    workflow = WORKFLOW.replace("on:\n", f"env:\n  {key}: attacker\non:\n", 1)
    _write_repository(tmp_path, workflow)

    assert any("GitHub CLI" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_cli_env(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n    permissions:\n",
        "    runs-on: ubuntu-latest\n    env:\n      GH_HOST: attacker.example\n    permissions:\n",
        1,
    )
    _write_repository(tmp_path, workflow)

    assert any("GitHub CLI" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_step_cli_env(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        f"      - uses: {ACTION}\n        with:\n",
        f"      - uses: {ACTION}\n        env:\n          GH_HOST: attacker.example\n"
        "        with:\n",
        1,
    )
    _write_repository(tmp_path, workflow)

    assert any("canonical gate step" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_symlinked_codeowners(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    contents = codeowners.read_text(encoding="utf-8")
    codeowners.unlink()
    target = tmp_path / "OWNERS"
    target.write_text(contents, encoding="utf-8")
    codeowners.symlink_to("../OWNERS")

    assert _findings(tmp_path)


def test_review_gate_rejects_symlinked_workflow_ancestor(tmp_path: Path) -> None:
    github = tmp_path / ".github"
    github.mkdir(parents=True, exist_ok=True)
    real_workflows = tmp_path / "real-workflows"
    real_workflows.mkdir()
    (real_workflows / "codex-review.yml").write_text(WORKFLOW, encoding="utf-8")
    (github / "workflows").symlink_to("../real-workflows", target_is_directory=True)
    (github / "CODEOWNERS").write_text(
        "/.github/workflows/** @repository-owner\n/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )

    assert _findings(tmp_path)


def test_ai_review_workflow_must_be_single_path_semantically(tmp_path: Path) -> None:
    findings = _ai_review_workflow_findings(
        [".github/workflows/one.yml", ".github/workflows/two.yml"], tmp_path
    )

    assert any("exactly one" in item.message for item in findings)


def test_ai_review_workflow_must_be_single_path_in_schema() -> None:
    data = load_mapping(template_path())
    data["evidence"]["paths"]["ai_review_workflow"] = [
        ".github/workflows/one.yml",
        ".github/workflows/two.yml",
    ]

    findings = contract_findings(data)

    assert any(
        item.code == "schema.invalid" and item.path == "evidence.paths.ai_review_workflow"
        for item in findings
    )


def test_self_validator_governs_ai_review_policy() -> None:
    source = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    assert '"docs/AI_REVIEW_GOVERNANCE.md",' in source


def test_preflight_binds_marker_context_to_base_and_custom_context() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert 'export CODEX_REVIEW_CONTEXT="${BASE_SHA}:${CUSTOM_CONTEXT}"' in source


def test_preflight_verifies_codeowners_with_github() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert "repos/${REPO}/codeowners/errors?ref=${HEAD_SHA}" in source
    assert "verify_codeowners" in source


def test_request_and_wait_requires_explicit_review_label() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert '[[ "$MODE" == "request-and-wait" ]]' in source
    assert "event_label" in source
    assert "explicit ${REQUEST_LABEL} label event" in source


def test_preflight_clamps_polling_to_timeout() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert "if (( POLL_SECONDS > TIMEOUT_SECONDS )); then" in source
    assert 'POLL_SECONDS="$TIMEOUT_SECONDS"' in source


def test_review_gate_rejects_poll_interval_longer_than_timeout(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          request-label: codex:review\n",
        (
            "          request-label: codex:review\n"
            "          timeout-seconds: 30\n"
            "          poll-seconds: 3600\n"
        ),
        2,
    )
    _write_repository(tmp_path, workflow)
    assert _findings(tmp_path)


def test_review_gate_requires_namespace_wide_codeowners_rule(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("namespace rule" in item.message for item in _findings(tmp_path))


def test_review_gate_checks_every_existing_workflow_owner(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    extra = tmp_path / ".github" / "workflows" / "bypass.yml"
    extra.write_text("name: bypass\non: push\njobs: {}\n", encoding="utf-8")
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        codeowners.read_text(encoding="utf-8") + "/.github/workflows/bypass.yml\n",
        encoding="utf-8",
    )
    assert any("bypass.yml" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_matching_review_contexts(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          mode: request\n",
        "          mode: request\n          review-context: request-only\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("same review-context" in item.message for item in _findings(tmp_path))


def test_review_gate_accepts_matching_review_contexts(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          request-label: codex:review\n",
        "          request-label: codex:review\n          review-context: shared\n",
        2,
    )
    _write_repository(tmp_path, workflow)
    assert not _findings(tmp_path)


def test_review_gate_rejects_wait_job_without_explicit_read_only_event_guard(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.replace(
        f"    if: {WAIT_CONDITION}\n",
        "    if: github.event.pull_request.draft == false\n",
        1,
    )
    _write_repository(tmp_path, workflow)

    assert any("codex-review job condition" in item.message for item in _findings(tmp_path))
