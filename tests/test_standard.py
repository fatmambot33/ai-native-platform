"""Tests for canonical standard self-validation."""

from __future__ import annotations

import json

import yaml
from jsonschema import Draft202012Validator

from ai_native import load_schema
from validator.validate_standard import ROOT, validate_standard


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
