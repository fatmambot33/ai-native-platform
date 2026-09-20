"""Focused regressions for fail-closed inheritance schema hardening."""

import json
from pathlib import Path

import pytest

from ai_native_platform.inheritance import InheritanceError, validate_declaration

ROOT = Path(__file__).resolve().parents[1]


def _valid_declaration() -> dict:
    """Return a minimal valid v1 inheritance declaration."""
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": "v1.0.0",
        },
        "capabilities": {
            name: "inherit"
            for name in ("welcome", "troubleshooting", "update", "doctor")
        },
    }


def test_schema_contract_requires_platform_ref(tmp_path) -> None:
    """Canonical hardening must detect removal of the required provider ref."""
    schema = json.loads(
        (ROOT / "schemas/ai-native-derived.schema.json").read_text(encoding="utf-8")
    )
    schema["properties"]["platform"]["required"].remove("ref")
    schema_path = tmp_path / "ai-native-derived.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(InheritanceError, match="fail-closed contract"):
        validate_declaration(_valid_declaration(), schema_path=schema_path)
