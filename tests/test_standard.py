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
    assert "missing" in findings[0].message


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
