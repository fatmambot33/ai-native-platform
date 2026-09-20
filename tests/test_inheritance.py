"""Tests for the AI Native inheritance contract."""

import argparse
import copy
import json
from pathlib import Path

import pytest
import yaml

from ai_native_entry import _inheritance_findings
from ai_native_platform.inheritance import (
    InheritanceError,
    doctor,
    load_declaration,
    resolve,
    validate_declaration,
)

PLATFORM_REF = "b2793f9fae645df1bda7492da01627396fc5e29f"
ROOT = Path(__file__).resolve().parents[1]


def declaration() -> dict:
    """Return a minimal valid derived-repository declaration."""
    return {
        "version": 1,
        "platform": {"repository": "fatmambot33/ai-native-platform", "ref": PLATFORM_REF},
        "profile": "library",
        "capabilities": {
            name: "inherit" for name in ("welcome", "troubleshooting", "update", "doctor")
        },
        "ownership": {"local": ["src/local.py"]},
    }


def test_resolve_is_deterministic_and_records_provenance() -> None:
    candidate = declaration()
    assert resolve(candidate) == resolve(copy.deepcopy(candidate))
    welcome = resolve(candidate)["welcome"]
    assert welcome.enabled is True
    assert welcome.provenance == ("platform", "profile:library")


def test_composition_modes_record_selected_provenance() -> None:
    candidate = declaration()
    candidate["capabilities"].update(
        welcome="append", troubleshooting="override", doctor="disable"
    )
    candidate["extensions"] = {
        "welcome": ["welcome-local"],
        "troubleshooting": ["troubleshooting-local"],
    }
    resolved = resolve(candidate)
    assert resolved["welcome"].provenance == ("platform", "profile:library", "repository")
    assert resolved["troubleshooting"].provenance == ("repository",)
    assert resolved["doctor"].provenance == ("repository",)


def test_append_requires_local_content() -> None:
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "append"
    with pytest.raises(InheritanceError, match="requires local content"):
        validate_declaration(candidate)


def test_inherit_and_disable_reject_extensions() -> None:
    for mode in ("inherit", "disable"):
        candidate = declaration()
        candidate["capabilities"]["doctor"] = mode
        candidate["extensions"] = {"doctor": ["doctor-local"]}
        with pytest.raises(InheritanceError, match="cannot carry local content"):
            validate_declaration(candidate)


def test_unknown_contract_profile_capability_and_mode_fail_closed() -> None:
    for key, value in (("version", 2), ("profile", "unknown")):
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


def test_ownership_rejects_nonportable_paths_and_cross_owner_overlap() -> None:
    unsafe_paths = (
        "../outside",
        "..\\outside",
        "C:\\outside",
        "\\\\server\\share",
        "bad\0path",
        "CON",
        "CONIN$",
        "conout$.txt",
        "CON .txt",
        "COM1 .log",
        "aux .md",
        "COM¹",
        "lpt².log",
        "dir/aux.txt",
        "dir/file*",
        "dir/name.",
        "dir/name ",
        "a" * 256,
        "é" * 128,
    )
    for unsafe in unsafe_paths:
        candidate = declaration()
        candidate["ownership"] = {"local": [unsafe]}
        with pytest.raises(InheritanceError, match="unsafe ownership path"):
            validate_declaration(candidate)
    for managed, local in (
        ("docs", "docs/local.md"),
        ("README.md", "readme.md"),
        ("docs/café.md", "docs/café.md"),
    ):
        candidate = declaration()
        candidate["ownership"] = {"managed": [managed], "local": [local]}
        with pytest.raises(InheritanceError, match="ambiguous ownership"):
            validate_declaration(candidate)


def test_validate_declaration_uses_explicit_schema_path(tmp_path) -> None:
    """Canonical callers can validate against the schema from their own root."""
    schema_path = tmp_path / "derived.schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["canonical_only"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(InheritanceError, match="canonical_only"):
        validate_declaration(declaration(), schema_path=schema_path)


def test_loaded_canonical_starter_uses_sibling_schema(tmp_path) -> None:
    """A starter loaded from a checkout must use that checkout's schema."""
    schema = json.loads(
        (ROOT / "schemas/ai-native-derived.schema.json").read_text(encoding="utf-8")
    )
    schema["required"].append("canonical_only")
    schema_path = tmp_path / "schemas" / "ai-native-derived.schema.json"
    schema_path.parent.mkdir()
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    starter = tmp_path / "templates" / "derived.yaml"
    starter.parent.mkdir()
    starter.write_text(yaml.safe_dump(declaration()), encoding="utf-8")

    with pytest.raises(InheritanceError, match="canonical_only"):
        validate_declaration(load_declaration(starter))


def test_canonical_schema_rejects_permissive_replacement(tmp_path) -> None:
    """A syntactically valid schema cannot silently drop the v1 contract."""
    schema_path = tmp_path / "ai-native-derived.schema.json"
    schema_path.write_text("{}", encoding="utf-8")

    with pytest.raises(InheritanceError, match="fail-closed contract"):
        validate_declaration(declaration(), schema_path=schema_path)


def test_canonical_schema_resolves_references_with_runtime_semantics(tmp_path) -> None:
    """Canonical reference checks must use the runtime JSON Schema resolver."""
    schema = json.loads(
        (ROOT / "schemas/ai-native-derived.schema.json").read_text(encoding="utf-8")
    )
    schema["properties"]["capabilities"]["properties"]["welcome"]["$ref"] = (
        "#/$defs/mode%2Fmissing"
    )
    schema_path = tmp_path / "ai-native-derived.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(Exception, match="mode%2Fmissing"):
        validate_declaration(declaration(), schema_path=schema_path)


def test_large_ownership_manifest_validates() -> None:
    candidate = declaration()
    candidate["ownership"] = {"local": [f"src/module-{index}.py" for index in range(2000)]}
    validate_declaration(candidate)


def test_platform_reference_semver_is_fail_closed() -> None:
    valid_refs = (
        "1.2.3",
        "v1.2.3",
        "1.2.3-alpha.1",
        "1.2.3+build.7",
        "1.2.3-rc.1+build.7",
    )
    for valid in valid_refs:
        candidate = declaration()
        candidate["platform"]["ref"] = valid
        validate_declaration(candidate)
    invalid_refs = ("main", "01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "1.2.3-alpha..1")
    for invalid in invalid_refs:
        candidate = declaration()
        candidate["platform"]["ref"] = invalid
        with pytest.raises(InheritanceError):
            validate_declaration(candidate)


def test_platform_repository_is_fail_closed() -> None:
    candidate = declaration()
    candidate["platform"]["repository"] = "example/other"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)


def test_duplicate_yaml_keys_fail_closed(tmp_path) -> None:
    path = tmp_path / "derived.yaml"
    path.write_text("capabilities:\n  welcome: inherit\n  welcome: disable\n", encoding="utf-8")
    with pytest.raises(InheritanceError, match="duplicate declaration key"):
        load_declaration(path)


def _write_declaration(root, candidate=None):
    path = root / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(candidate or declaration()), encoding="utf-8")
    return path


def test_doctor_accepts_compliant_derived_repository(tmp_path) -> None:
    _write_declaration(tmp_path)
    assert doctor(tmp_path) == []


def test_doctor_reports_invalid_declaration_without_mutating(tmp_path) -> None:
    candidate = declaration()
    candidate["platform"]["ref"] = "main"
    path = _write_declaration(tmp_path, candidate)
    original = path.read_text(encoding="utf-8")
    findings = doctor(tmp_path)
    assert [finding.code for finding in findings] == ["inheritance.invalid"]
    assert path.read_text(encoding="utf-8") == original


def test_doctor_reports_invalid_utf8_as_finding(tmp_path) -> None:
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_parser_recursion_as_finding(tmp_path) -> None:
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text("value: " + "[" * 600 + "0" + "]" * 600, encoding="utf-8")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_rejects_declaration_and_directory_symlinks(tmp_path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "derived.yaml").write_text(yaml.safe_dump(declaration()), encoding="utf-8")
    for target_directory in (False, True):
        root = tmp_path / ("repo-dir" if target_directory else "repo-file")
        root.mkdir()
        try:
            if target_directory:
                (root / ".ai-native").symlink_to(outside, target_is_directory=True)
            else:
                (root / ".ai-native").mkdir()
                (root / ".ai-native" / "derived.yaml").symlink_to(outside / "derived.yaml")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks are unavailable on this platform")
        assert [finding.code for finding in doctor(root)] == ["inheritance.invalid"]


def test_doctor_reports_broken_declaration_symlink(tmp_path) -> None:
    declaration_path = tmp_path / ".ai-native" / "derived.yaml"
    declaration_path.parent.mkdir()
    try:
        declaration_path.symlink_to(tmp_path / "missing-derived.yaml")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_presence_check_failure(tmp_path, monkeypatch) -> None:
    from ai_native_platform import inheritance

    original_lstat = inheritance.Path.lstat

    def failing_lstat(path):
        if path.name == "derived.yaml":
            raise PermissionError("denied")
        return original_lstat(path)

    monkeypatch.setattr(inheritance.Path, "lstat", failing_lstat)
    (tmp_path / ".ai-native").mkdir()
    assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_reports_corrupt_schema_and_reference(tmp_path, monkeypatch) -> None:
    from ai_native_platform import inheritance

    schema = tmp_path / "schema.json"
    monkeypatch.setattr(inheritance, "_schema_path", lambda: schema)
    _write_declaration(tmp_path)
    malformed_schemas = (
        "{",
        json.dumps({"type": 3}),
        json.dumps({"$ref": "#/$defs/missing"}),
    )
    for content in malformed_schemas:
        schema.write_text(content, encoding="utf-8")
        assert [finding.code for finding in doctor(tmp_path)] == ["inheritance.invalid"]


def test_doctor_preserves_non_derived_repository_compatibility(tmp_path) -> None:
    assert doctor(tmp_path) == []
    (tmp_path / ".ai-native").write_text("legacy marker", encoding="utf-8")
    assert doctor(tmp_path) == []


def test_entrypoint_reports_root_resolution_failure(tmp_path) -> None:
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(loop)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")
    args = argparse.Namespace(root=str(loop), manifest="AI_NATIVE_PLATFORM.yaml")
    findings = _inheritance_findings(args)
    assert [finding.code for finding in findings] == ["inheritance.invalid"]