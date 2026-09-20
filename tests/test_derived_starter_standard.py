"""Regression tests for canonical derived-starter validation."""

from __future__ import annotations

from pathlib import Path

from validator.validate_standard import _append_derived_starter_finding

VALID_REF = "c230f7398ea936e98e4a0ceecd5b069b9248d50e"


def _write_starter(root: Path, content: str) -> None:
    """Write one derived starter under a minimal canonical-root layout."""
    path = root / "templates" / "derived.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")


def _findings(root: Path):
    """Return findings produced for the derived starter at ``root``."""
    findings = []
    _append_derived_starter_finding(root, findings)
    return findings


def test_valid_derived_starter_passes(tmp_path: Path) -> None:
    _write_starter(
        tmp_path,
        f"""version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: {VALID_REF}
profile: library
capabilities:
  welcome: inherit
  troubleshooting: inherit
  update: inherit
  doctor: inherit
ownership:
  local: []
""",
    )

    assert _findings(tmp_path) == []


def test_malformed_derived_starter_fails_closed(tmp_path: Path) -> None:
    _write_starter(tmp_path, "version: [\n")

    findings = _findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "standard.derived_template_invalid"
    assert findings[0].path == "templates/derived.yaml"


def test_schema_invalid_derived_starter_fails_closed(tmp_path: Path) -> None:
    _write_starter(
        tmp_path,
        f"""version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: {VALID_REF}
profile: library
capabilities:
  welcome: inherit
  troubleshooting: inherit
  update: inherit
ownership:
  local: []
""",
    )

    findings = _findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "standard.derived_template_invalid"
    assert "doctor" in findings[0].message


def test_cross_field_invalid_derived_starter_fails_closed(tmp_path: Path) -> None:
    _write_starter(
        tmp_path,
        f"""version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: {VALID_REF}
profile: library
capabilities:
  welcome: append
  troubleshooting: inherit
  update: inherit
  doctor: inherit
ownership:
  local: []
""",
    )

    findings = _findings(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "standard.derived_template_invalid"
    assert "welcome: append requires local content" in findings[0].message
