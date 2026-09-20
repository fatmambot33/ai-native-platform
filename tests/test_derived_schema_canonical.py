"""Regression tests for canonical validation of the inheritance schema."""

from __future__ import annotations

from validator.validate_standard import _append_schema_finding


def test_derived_schema_is_parsed_and_meta_validated(tmp_path) -> None:
    """Reject a malformed derived schema during canonical validation."""
    relative = "schemas/ai-native-derived.schema.json"
    schema_path = tmp_path / relative
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text('{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": 42}\n', encoding="utf-8")

    findings = []
    _append_schema_finding(tmp_path, relative, findings)

    assert len(findings) == 1
    assert findings[0].code == "standard.schema_invalid"
    assert findings[0].path == relative
