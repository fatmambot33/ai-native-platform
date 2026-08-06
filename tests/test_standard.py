"""Tests for canonical standard self-validation."""

from __future__ import annotations

import json
import re

import yaml
from jsonschema import Draft202012Validator

from ai_native import load_schema
from validator.validate_standard import ROOT, validate_standard

IMMUTABLE_SHA = re.compile(r"[0-9a-f]{40}")


def test_canonical_standard_passes() -> None:
    assert validate_standard(ROOT) == []


def test_schema_is_valid_draft_2020_12() -> None:
    schema = load_schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


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
