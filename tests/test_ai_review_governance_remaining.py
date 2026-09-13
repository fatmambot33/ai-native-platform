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

GATE_REF = "96f34eeb234cb9c4cebf68749a8fcbca969f5865"
ACTION = f"fatmambot33/ai-native-platform/actions/codex-review-gate@{GATE_REF}"
WORKFLOW = f"""name: Codex review governance
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]
  pull_request_target:
    types: [labeled]
  pull_request_review:
    types: [dismissed]
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
    if: (github.event_name == 'pull_request' || github.event_name == 'pull_request_review')
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
        "/.github/workflows/** @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )


def _findings(root: Path) -> list:
    return _single_ai_review_workflow_findings(
        ".github/workflows/codex-review.yml", root
    )


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
def test_review_gate_rejects_pr_filters(
    tmp_path: Path, event: str, key: str
) -> None:
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
        "    runs-on: ubuntu-latest\n    env:\n      GH_HOST: attacker.example\n"
        "    permissions:\n",
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
        "/.github/workflows/** @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
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
        item.code == "schema.invalid"
        and item.path == "evidence.paths.ai_review_workflow"
        for item in findings
    )


def test_self_validator_governs_ai_review_policy() -> None:
    source = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    assert '"docs/AI_REVIEW_GOVERNANCE.md",' in source
