"""Tests for the AI Native inheritance contract."""

import copy

import pytest
import yaml

from tools.inheritance import InheritanceError, doctor, load_declaration, resolve, validate_declaration


def declaration() -> dict:
    """Return a minimal valid derived-repository declaration."""
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": "v0.3.0",
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
    """Identical declarations resolve to identical explicit provenance."""
    candidate = declaration()
    assert resolve(candidate) == resolve(copy.deepcopy(candidate))
    welcome = resolve(candidate)["welcome"]
    assert welcome.enabled is True
    assert welcome.provenance == ("platform", "profile:library")


def test_append_requires_and_records_local_content() -> None:
    """Append is explicit and cannot silently omit repository content."""
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "append"
    with pytest.raises(InheritanceError, match="requires local content"):
        validate_declaration(candidate)
    candidate["extensions"] = {"welcome": ["docs/welcome-local.md"]}
    resolved = resolve(candidate)["welcome"]
    assert resolved.extensions == ("docs/welcome-local.md",)
    assert resolved.provenance[-1] == "repository"


def test_inherit_and_disable_reject_extensions() -> None:
    """Modes without local composition reject contradictory extension data."""
    for mode in ("inherit", "disable"):
        candidate = declaration()
        candidate["capabilities"]["doctor"] = mode
        candidate["extensions"] = {"doctor": ["doctor-local"]}
        with pytest.raises(InheritanceError, match="cannot carry local content"):
            validate_declaration(candidate)


def test_unknown_contract_profile_capability_and_mode_fail_closed() -> None:
    """Unsupported contract vocabulary never falls through as local behavior."""
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
    """Ownership paths are portable, repository-relative, and unambiguous."""
    for unsafe in ("../outside", "..\\outside", "C:\\outside", "\\\\server\\share"):
        candidate = declaration()
        candidate["ownership"] = {"local": [unsafe]}
        with pytest.raises(InheritanceError, match="unsafe ownership path"):
            validate_declaration(candidate)

    candidate = declaration()
    candidate["ownership"] = {"managed": ["docs"], "local": ["docs/local.md"]}
    with pytest.raises(InheritanceError, match="ambiguous ownership"):
        validate_declaration(candidate)


def test_platform_reference_and_repository_are_fail_closed() -> None:
    """Derived repositories must pin the canonical platform immutably."""
    candidate = declaration()
    candidate["platform"]["ref"] = "main"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
    candidate = declaration()
    candidate["platform"]["repository"] = "example/other"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)


def test_duplicate_yaml_keys_fail_closed(tmp_path) -> None:
    """Conflicting duplicate YAML keys are never silently overwritten."""
    path = tmp_path / "derived.yaml"
    path.write_text("capabilities:\n  welcome: inherit\n  welcome: disable\n", encoding="utf-8")
    with pytest.raises(InheritanceError, match="duplicate declaration key"):
        load_declaration(path)


def test_doctor_accepts_compliant_derived_repository(tmp_path) -> None:
    """Doctor reports no findings for a valid opted-in repository."""
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(declaration()), encoding="utf-8")
    assert doctor(tmp_path) == []


def test_doctor_reports_invalid_declaration_without_mutating(tmp_path) -> None:
    """Doctor fails closed and leaves an invalid declaration untouched."""
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
    """Declaration decoding failures are deterministic doctor findings."""
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_broken_declaration_symlink(tmp_path) -> None:
    """A present but unreadable declaration entry fails closed."""
    declaration_path = tmp_path / ".ai-native" / "derived.yaml"
    declaration_path.parent.mkdir()
    try:
        declaration_path.symlink_to(tmp_path / "missing-derived.yaml")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_preserves_non_derived_repository_compatibility(tmp_path) -> None:
    """Repositories that do not opt into inheritance retain existing behavior."""
    assert doctor(tmp_path) == []
