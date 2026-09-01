"""Tests for the product manifest validator."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from ai_native import (
    command_init,
    contract_findings,
    load_mapping,
    required_evidence_keys,
    template_path,
    validate_manifest,
)

AI_REVIEW_GATE_REF = "cd1f286222a286508c962288671c1f6c97b52d95"
AI_REVIEW_ACTION = (
    "fatmambot33/ai-native-platform/actions/codex-review-gate@" + AI_REVIEW_GATE_REF
)
AI_REVIEW_WORKFLOW = """name: Codex review governance
on:
  pull_request:
  pull_request_target:
  pull_request_review:
    types: [dismissed]
permissions:
  contents: read
concurrency:
  group: codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  request:
    if: github.event_name == 'pull_request_target'
    permissions:
      contents: read
      issues: write
      pull-requests: read
    steps:
      - uses: AI_REVIEW_ACTION
        with:
          token: ${{ github.token }}
          pr-number: ${{ github.event.pull_request.number }}
          head-sha: ${{ github.event.pull_request.head.sha }}
          mode: request
  codex-review:
    if: (github.event_name == 'pull_request' || github.event_name == 'pull_request_review')
    permissions:
      contents: read
      issues: read
      pull-requests: read
    steps:
      - uses: AI_REVIEW_ACTION
        with:
          token: ${{ github.token }}
          pr-number: ${{ github.event.pull_request.number }}
          head-sha: ${{ github.event.pull_request.head.sha }}
          mode: wait
""".replace("AI_REVIEW_ACTION", AI_REVIEW_ACTION)


def _template() -> dict:
    return load_mapping(template_path())


def _enable_ai_review(
    data: dict,
    value: str | list[str] = ".github/workflows/codex-review.yml",
) -> None:
    data["evidence"]["paths"]["ai_review_workflow"] = value


def _materialize_evidence(root: Path, data: dict) -> None:
    paths = data["evidence"]["paths"]
    for key in required_evidence_keys(data):
        declaration = paths[key]
        declarations = [declaration] if isinstance(declaration, str) else declaration
        for relative in declarations:
            path = root / relative
            if path.suffix or path.name.startswith("."):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"evidence for {key}\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / ".keep").write_text("evidence\n", encoding="utf-8")

    ai_review = paths.get("ai_review_workflow")
    ai_reviews = [ai_review] if isinstance(ai_review, str) else ai_review or []
    for relative in ai_reviews:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(AI_REVIEW_WORKFLOW, encoding="utf-8")
    if ai_reviews:
        codeowners = root / ".github" / "CODEOWNERS"
        codeowners.parent.mkdir(parents=True, exist_ok=True)
        codeowners.write_text(
            "/.github/workflows/** @repository-owner\n"
            "/.github/CODEOWNERS @repository-owner\n",
            encoding="utf-8",
        )


def _validate_ai_review_text(tmp_path: Path, workflow_text: str) -> list:
    data = _template()
    _enable_ai_review(data)
    _materialize_evidence(tmp_path, data)
    workflow = tmp_path / data["evidence"]["paths"]["ai_review_workflow"]
    workflow.write_text(workflow_text, encoding="utf-8")
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return validate_manifest(manifest, tmp_path)[1]


def test_starter_template_contract_is_valid() -> None:
    data = _template()

    assert "mcp" not in data["interfaces"]
    assert "ai_review_workflow" not in data["evidence"]["paths"]
    assert contract_findings(data) == []


def test_complete_repository_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_mcp_declaration_is_optional() -> None:
    data = _template()

    assert "mcp" not in data["interfaces"]
    assert contract_findings(data) == []


def test_mcp_evidence_is_required_only_when_enabled() -> None:
    data = _template()
    data["interfaces"]["mcp"] = False
    assert "mcp" not in required_evidence_keys(data)

    data["interfaces"]["mcp"] = True
    assert "mcp" in required_evidence_keys(data)


def test_agent_tool_accepts_plugin_without_mcp_declaration() -> None:
    data = _template()
    data["product"]["profile"] = "agent-tool"
    data["plugin"]["enabled"] = True
    data["interfaces"]["plugin"] = True

    assert "mcp" not in data["interfaces"]
    assert contract_findings(data) == []


def test_security_scan_requires_generic_security_evidence() -> None:
    keys = required_evidence_keys(_template())

    assert "security_evidence" in keys
    assert "security_workflow" not in keys


def test_ai_review_workflow_is_opt_in_for_version_one_manifests(tmp_path: Path) -> None:
    data = _template()
    assert "ai_review_workflow" not in required_evidence_keys(data)
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_missing_declared_ai_review_workflow_fails(tmp_path: Path) -> None:
    data = _template()
    _enable_ai_review(data)
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)
    (tmp_path / data["evidence"]["paths"]["ai_review_workflow"]).unlink()

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.path_missing"
        and finding.path == "evidence.paths.ai_review_workflow"
        for finding in findings
    )


def test_ai_review_evidence_must_be_a_trusted_workflow(tmp_path: Path) -> None:
    data = _template()
    _enable_ai_review(data)
    _materialize_evidence(tmp_path, data)
    data["evidence"]["paths"]["ai_review_workflow"] = "README.md"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.ai_review_workflow_invalid"
        and finding.path == "evidence.paths.ai_review_workflow"
        for finding in findings
    )


def test_ai_review_workflow_rejects_writable_status_api(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace(
            "permissions:\n  contents: read",
            "permissions:\n  contents: read\n  statuses: write",
            1,
        ),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_write_all_permissions(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace("permissions:\n  contents: read", "permissions: write-all", 1),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_comment_spoofed_semantics(tmp_path: Path) -> None:
    fake_workflow = """name: fake
on:
  workflow_dispatch:
jobs:
  unrelated:
    runs-on: ubuntu-latest
    steps:
      - run: echo safe
# pull_request:
# pull_request_target:
# pull_request_review:
# codex-review:
# mode: request
# mode: wait
# issues: write
# issues: read
# pull-requests: read
# github.event_name == 'pull_request_target'
# github.event_name == 'pull_request'
# cancel-in-progress: true
# uses: AI_REVIEW_ACTION
""".replace("AI_REVIEW_ACTION", AI_REVIEW_ACTION)

    findings = _validate_ai_review_text(tmp_path, fake_workflow)

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_untrusted_gate_ref(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace(AI_REVIEW_GATE_REF, "0" * 40),
    )

    assert any(
        finding.code == "evidence.ai_review_workflow_invalid"
        and "untrusted gate revision" in finding.message
        for finding in findings
    )


def test_ai_review_workflow_accepts_multiple_paths(tmp_path: Path) -> None:
    data = _template()
    _enable_ai_review(
        data,
        [
            ".github/workflows/codex-review.yml",
            ".github/workflows/codex-review-secondary.yml",
        ],
    )
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_ai_review_workflow_requires_token_input(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace("          token: ${{ github.token }}\n", "", 1),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_pr_head_execution_in_request_job(tmp_path: Path) -> None:
    unsafe = AI_REVIEW_WORKFLOW.replace(
        "    steps:\n      - uses: " + AI_REVIEW_ACTION,
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          ref: ${{ github.event.pull_request.head.sha }}\n"
        "      - uses: "
        + AI_REVIEW_ACTION,
        1,
    )

    findings = _validate_ai_review_text(tmp_path, unsafe)

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_skipped_gate_step(tmp_path: Path) -> None:
    unsafe = AI_REVIEW_WORKFLOW.replace(
        "      - uses: " + AI_REVIEW_ACTION,
        "      - uses: " + AI_REVIEW_ACTION + "\n        if: false",
        1,
    )

    findings = _validate_ai_review_text(tmp_path, unsafe)

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_ignored_gate_failure(tmp_path: Path) -> None:
    unsafe = AI_REVIEW_WORKFLOW.replace(
        "      - uses: " + AI_REVIEW_ACTION,
        "      - uses: " + AI_REVIEW_ACTION + "\n        continue-on-error: true",
        1,
    )

    findings = _validate_ai_review_text(tmp_path, unsafe)

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_rejects_false_job_condition(tmp_path: Path) -> None:
    canonical = (
        "if: (github.event_name == 'pull_request' || "
        "github.event_name == 'pull_request_review')"
    )
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace(canonical, canonical + " && false"),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_requires_synchronize_event(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace("  pull_request:\n", "  pull_request:\n    types: [opened]\n"),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_ai_review_workflow_separates_event_concurrency(tmp_path: Path) -> None:
    findings = _validate_ai_review_text(
        tmp_path,
        AI_REVIEW_WORKFLOW.replace(
            "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}",
            "codex-review-${{ github.event.pull_request.number }}",
        ),
    )

    assert any(finding.code == "evidence.ai_review_workflow_invalid" for finding in findings)


def test_codex_review_gate_checks_unresolved_threads() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")

    assert "reviewThreads(first: 100" in script
    assert "has_unresolved_codex_threads" in script
    assert ".isResolved == false" in script
    assert "all Codex review threads are resolved" in script


def test_workflow_security_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    data["evidence"]["paths"]["security_evidence"] = ".github/workflows/codeql.yml"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_native_ruleset_security_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    data["evidence"]["paths"]["security_evidence"] = ".github/SECURITY_ENFORCEMENT.md"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_legacy_security_workflow_key_is_not_an_alias(tmp_path: Path) -> None:
    data = _template()
    _materialize_evidence(tmp_path, data)
    data["evidence"]["paths"].pop("security_evidence")
    data["evidence"]["paths"]["security_workflow"] = ".github/SECURITY_ENFORCEMENT.md"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.declaration_missing"
        and finding.path == "evidence.paths.security_evidence"
        for finding in findings
    )


def test_unknown_controlled_field_is_rejected() -> None:
    data = _template()
    data["product"]["unexpected"] = True

    findings = contract_findings(data)

    assert any(finding.code == "schema.invalid" for finding in findings)


def test_floating_standard_ref_is_rejected() -> None:
    data = _template()
    data["standard"]["ref"] = "main"

    findings = contract_findings(data)

    assert any(finding.code == "standard.ref_not_immutable" for finding in findings)


def test_plugin_profile_requires_plugin_evidence(tmp_path: Path) -> None:
    data = copy.deepcopy(_template())
    data["product"]["profile"] = "plugin"
    data["plugin"]["enabled"] = True
    data["plugin"]["codex"] = {"supported": True, "marketplace": True}
    data["plugin"]["discovery"] = {
        "entry_points": True,
        "manifest": True,
        "capabilities": True,
    }
    data["interfaces"].update({"sdk": False, "plugin": True})
    data["evidence"]["paths"].update(
        {
            "plugin_manifest": ".codex-plugin/plugin.json",
            "plugin_tests": "tests/test_plugin.py",
        }
    )
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)
    (tmp_path / ".codex-plugin/plugin.json").unlink()

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.path_missing"
        and finding.path == "evidence.paths.plugin_manifest"
        for finding in findings
    )


def test_init_copies_canonical_template(tmp_path: Path) -> None:
    class Args:
        destination = str(tmp_path / "AI_NATIVE_PLATFORM.yaml")
        force = False

    assert command_init(Args()) == 0
    generated = load_mapping(Path(Args.destination))
    assert generated["version"] == 1
    assert "mcp" not in generated["interfaces"]
    assert "ai_review_workflow" not in generated["evidence"]["paths"]
