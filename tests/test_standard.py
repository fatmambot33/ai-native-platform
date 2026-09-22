"""Tests for canonical standard self-validation."""

from __future__ import annotations

import json
import re

import tomli as tomllib
import yaml
from jsonschema import Draft202012Validator

from ai_native import load_schema
from validator.validate_standard import (
    REQUIRED_FILES,
    ROOT,
    _append_packaged_schema_finding,
    _append_schema_finding,
    validate_standard,
)

IMMUTABLE_SHA = re.compile(r"[0-9a-f]{40}")


def test_canonical_standard_passes() -> None:
    assert validate_standard(ROOT) == []


def test_schema_is_valid_draft_2020_12() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_derived_schema_rejects_unresolved_local_reference(tmp_path) -> None:
    """Canonical validation must reject a syntactically valid broken local ref."""
    relative = "schemas/ai-native-derived.schema.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": {},
                "$ref": "#/$defs/missing",
            }
        ),
        encoding="utf-8",
    )

    findings = []
    _append_schema_finding(tmp_path, relative, findings)

    assert len(findings) == 1
    assert findings[0].code == "standard.schema_invalid"
    assert findings[0].path == relative
    assert "Unresolved local schema reference" in findings[0].message


def test_packaged_derived_schema_is_required_canonical_artifact() -> None:
    assert "ai_native_platform/schemas/ai-native-derived.schema.json" in REQUIRED_FILES


def test_packaged_derived_schema_must_match_canonical_schema(tmp_path) -> None:
    """Canonical validation must reject drift in the schema shipped by the wheel."""
    canonical = tmp_path / "schemas/ai-native-derived.schema.json"
    packaged = tmp_path / "ai_native_platform/schemas/ai-native-derived.schema.json"
    canonical.parent.mkdir(parents=True)
    packaged.parent.mkdir(parents=True)
    canonical.write_text('{"type": "object"}\n', encoding="utf-8")
    packaged.write_text('{}\n', encoding="utf-8")

    findings = []
    _append_packaged_schema_finding(tmp_path, findings)

    assert len(findings) == 1
    assert findings[0].code == "standard.schema_copy_drift"
    assert findings[0].path == "ai_native_platform/schemas/ai-native-derived.schema.json"


def test_packaged_derived_schema_accepts_exact_copy(tmp_path) -> None:
    """Canonical validation must accept an exact packaged schema copy."""
    canonical = tmp_path / "schemas/ai-native-derived.schema.json"
    packaged = tmp_path / "ai_native_platform/schemas/ai-native-derived.schema.json"
    canonical.parent.mkdir(parents=True)
    packaged.parent.mkdir(parents=True)
    content = '{"type": "object"}\n'
    canonical.write_text(content, encoding="utf-8")
    packaged.write_text(content, encoding="utf-8")

    findings = []
    _append_packaged_schema_finding(tmp_path, findings)

    assert findings == []


def test_derived_starter_is_required_canonical_artifact() -> None:
    assert "templates/derived.yaml" in REQUIRED_FILES


def test_issue_form_uses_yaml_form_keys() -> None:
    issue_form = yaml.safe_load(
        (ROOT / ".github/ISSUE_TEMPLATE/ai-improvement.yml").read_text(encoding="utf-8")
    )
    assert set(("name", "description", "body")) <= set(issue_form)
    assert "about" not in issue_form


def test_schema_json_is_stably_formatted() -> None:
    path = ROOT / "schemas/ai-native-platform.schema.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.read_text(encoding="utf-8") == json.dumps(data, indent=2) + "\n"


def test_public_license_is_apache_2_0() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    license_file = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert pyproject["project"]["license"]["text"] == "Apache-2.0"
    assert "Apache License" in license_file
    assert "Version 2.0, January 2004" in license_file


def test_codeql_uploads_when_public_and_retains_private_fallback() -> None:
    workflow = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
    for token in (
        "security-events: write",
        "github.event.repository.private",
        "'never' || 'always'",
        "actions/upload-artifact@v4",
    ):
        assert token in workflow


def test_reusable_codex_gate_implementation_is_required() -> None:
    assert "actions/codex-review-gate/action.yml" in REQUIRED_FILES
    assert "actions/codex-review-gate/codex-review-gate.sh" in REQUIRED_FILES


def test_standard_self_validation_uses_effective_codeowners_rules() -> None:
    source = (ROOT / "validator/validate_standard.py").read_text(encoding="utf-8")

    assert "_codeowners_effective_owners" in source
    assert "token not in codeowners" not in source


def test_real_consumer_registry_is_immutable_and_diverse() -> None:
    registry = yaml.safe_load(
        (ROOT / "consumers/registry.yaml").read_text(encoding="utf-8")
    )
    consumers = registry["consumers"]
    assert IMMUTABLE_SHA.fullmatch(registry["standard_ref"])
    assert len(consumers) >= 3
    assert len({consumer["repository"] for consumer in consumers}) == len(consumers)
    assert {consumer["profile"] for consumer in consumers} >= {
        "agent-tool",
        "full-platform",
    }
    for consumer in consumers:
        assert IMMUTABLE_SHA.fullmatch(consumer["ref"])
        assert consumer["manifest"] == "AI_NATIVE_PLATFORM.yaml"


def test_consumer_registry_is_codeowner_protected() -> None:
    codeowners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    source = (ROOT / "validator/validate_standard.py").read_text(encoding="utf-8")

    assert "/consumers/registry.yaml @fatmambot33" in codeowners
    assert '"consumers/registry.yaml",' in source


def test_standard_requests_review_only_after_ci_is_green() -> None:
    standard = yaml.safe_load(
        (ROOT / "standard/AI_NATIVE_PLATFORM.yaml").read_text(encoding="utf-8")
    )

    assert standard["governance"]["ai_review"]["request_while_ci_runs"] is False


def test_consumer_workflow_validates_registry_entries() -> None:
    workflow = (ROOT / ".github/workflows/consumer-conformance.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        "consumers/registry.yaml",
        "ai-native validate",
        "matrix.repository",
        "matrix.ref",
        "EXPECTED_STANDARD_REF",
        "workflow_call",
    ):
        assert token in workflow


def test_release_workflow_is_idempotent_verifiable_and_prerelease() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    for token in (
        "uses: ./.github/workflows/consumer-conformance.yml",
        "gh release view",
        "python tools/release_artifacts.py dist",
        "Provenance digest mismatch",
        "spdxVersion",
        "github.event.repository.private == false",
        "actions/attest-build-provenance@v3",
        "git tag -a",
        "gh release create",
        "--prerelease",
        "--verify-tag",
    ):
        assert token in workflow


def test_branch_freshness_is_scoped_to_ai_review() -> None:
    standard = yaml.safe_load(
        (ROOT / "standard/AI_NATIVE_PLATFORM.yaml").read_text(encoding="utf-8")
    )
    assert "branch_up_to_date" not in standard["release_gates"]
    assert "branch_up_to_date" in standard["governance"]["ai_review"]["release_gates"]


def test_root_agent_policy_is_codeowner_protected() -> None:
    codeowners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = (ROOT / "validator/validate_standard.py").read_text(encoding="utf-8")
    assert "/AGENTS.md @fatmambot33" in codeowners
    assert '"AGENTS.md",' in validator
