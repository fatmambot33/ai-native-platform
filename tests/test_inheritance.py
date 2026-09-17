"""Tests for the AI Native inheritance contract."""

import copy
import json

import pytest
import yaml

from ai_native_platform.inheritance import (
    InheritanceError,
    doctor,
    load_declaration,
    resolve,
    validate_declaration,
)

PLATFORM_REF = "b2793f9fae645df1bda7492da01627396fc5e29f"


def declaration() -> dict:
    """Return a minimal valid derived-repository declaration."""
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": PLATFORM_REF,
        },
        "profile": "library",
        "capabilities": {
            "welcome": "inherit",
            "troubleshooting": "inherit",
            "update": "inherit",
            "doctor": "inherit",
        },
        "ownership": {"local": ["src/local.py"]},
    }


def test_resolve_is_deterministic_and_records_provenance() -> None:
    candidate = declaration()
    assert resolve(candidate) == resolve(copy.deepcopy(candidate))
    welcome = resolve(candidate)["welcome"]
    assert welcome.enabled is True
    assert welcome.provenance == ("platform", "profile:library")


def test_append_requires_and_records_local_content() -> None:
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "append"
    with pytest.raises(InheritanceError, match="requires local content"):
        validate_declaration(candidate)
    candidate["extensions"] = {"welcome": ["docs/welcome-local.md"]}
    resolved = resolve(candidate)["welcome"]
    assert resolved.extensions == ("docs/welcome-local.md",)
    assert resolved.provenance[-1] == "repository"


def test_inherit_and_disable_reject_extensions() -> None:
    for mode in ("inherit", "disable"):
        candidate = declaration()
        candidate["capabilities"]["doctor"] = mode
        candidate["extensions"] = {"doctor": ["doctor-local"]}
        with pytest.raises(InheritanceError, match="cannot carry local content"):
            validate_declaration(candidate)


def test_unknown_contract_profile_capability_and_mode_fail_closed() -> None:
    mutations = [("version", 2), ("profile", "unknown")]
    for key, value in mutations:
        candidate = declaration()
        candidate[key] = value
        with pytest.raises(InheritanceError):
            validate_declaration(candidate)
    candidate = declaration()
    candidate["capabilities"]["extra"] = "inherit"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "magic"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)


def test_ownership_rejects_portable_escape_and_cross_owner_overlap() -> None:
    for unsafe in ("../outside", "..\\outside", "C:\\outside", "\\\\server\\share", "bad\0path"):
        candidate = declaration()
        candidate["ownership"] = {"local": [unsafe]}
        with pytest.raises(InheritanceError, match="unsafe ownership path"):
            validate_declaration(candidate)

    for managed, local in (("docs", "docs/local.md"), ("README.md", "readme.md")):
        candidate = declaration()
        candidate["ownership"] = {"managed": [managed], "local": [local]}
        with pytest.raises(InheritanceError, match="ambiguous ownership"):
            validate_declaration(candidate)


def test_platform_reference_and_repository_are_fail_closed() -> None:
    candidate = declaration()
    candidate["platform"]["ref"] = "main"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
    candidate = declaration()
    candidate["platform"]["repository"] = "example/other"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)


def test_duplicate_yaml_keys_fail_closed(tmp_path) -> None:
    path = tmp_path / "derived.yaml"
    path.write_text("capabilities:\n  welcome: inherit\n  welcome: disable\n", encoding="utf-8")
    with pytest.raises(InheritanceError, match="duplicate declaration key"):
        load_declaration(path)


def test_doctor_accepts_compliant_derived_repository(tmp_path) -> None:
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(declaration()), encoding="utf-8")
    assert doctor(tmp_path) == []


def test_doctor_reports_invalid_declaration_without_mutating(tmp_path) -> None:
    candidate = declaration()
    candidate["platform"]["ref"] = "main"
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    original = yaml.safe_dump(candidate)
    path.write_text(original, encoding="utf-8")
    findings = doctor(tmp_path)
    assert [finding.code for finding in findings] == ["inheritance.invalid"]
    assert findings[0].path == ".ai-native/derived.yaml"
    assert path.read_text(encoding="utf-8") == original


def test_doctor_reports_invalid_utf8_as_finding(tmp_path) -> None:
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_broken_declaration_symlink(tmp_path) -> None:
    declaration_path = tmp_path / ".ai-native" / "derived.yaml"
    declaration_path.parent.mkdir()
    try:
        declaration_path.symlink_to(tmp_path / "missing-derived.yaml")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_presence_check_failure(tmp_path, monkeypatch) -> None:
    """Filesystem metadata failures become deterministic findings."""
    from ai_native_platform import inheritance

    original_lstat = inheritance.Path.lstat

    def failing_lstat(path):
        if path.name == "derived.yaml":
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(inheritance.Path, "lstat", failing_lstat)
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_corrupt_schema(tmp_path, monkeypatch) -> None:
    """A damaged installed schema fails closed instead of crashing doctor."""
    from ai_native_platform import inheritance

    schema = tmp_path / "schema.json"
    schema.write_text("{", encoding="utf-8")
    monkeypatch.setattr(inheritance, "_schema_path", lambda: schema)
    declaration_path = tmp_path / ".ai-native" / "derived.yaml"
    declaration_path.parent.mkdir()
    declaration_path.write_text(yaml.safe_dump(declaration()), encoding="utf-8")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]

    schema.write_text(json.dumps({"type": 3}), encoding="utf-8")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_preserves_non_derived_repository_compatibility(tmp_path) -> None:
    assert doctor(tmp_path) == []
