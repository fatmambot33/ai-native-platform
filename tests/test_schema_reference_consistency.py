"""Regression tests for shared derived-schema reference resolution."""

from __future__ import annotations

import json

from validator.validate_standard import _append_schema_finding


def test_canonical_validation_uses_runtime_json_pointer_semantics(tmp_path) -> None:
    """Reject percent-encoded pointer tokens that runtime resolution cannot resolve."""
    relative = "schemas/ai-native-derived.schema.json"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$defs": {"a/b": {"type": "string"}},
                "$ref": "#/$defs/a%2Fb",
            }
        ),
        encoding="utf-8",
    )

    findings = []
    _append_schema_finding(tmp_path, relative, findings)

    assert len(findings) == 1
    assert findings[0].code == "standard.schema_invalid"
    assert findings[0].path == relative
