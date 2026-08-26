"""Tests for the product manifest validator."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from ai_native import (
    command_init,
    contract_findings,
    load_mapping,
    required_evidence_keys,
    template_path,
    validate_manifest,
)


def _template() -> dict:
    return load_mapping(template_path())


def _materialize_evidence(root: Path, data: dict) -> None:
    paths = data["evidence"]["paths"]
    for key in required_evidence_keys(data):
        declaration = paths[key]
        declarations = [declaration] if isinstance(declaration, str) else declaration
        for relative in declarations:
            path = root / relative
            if path.suffix or path.name.startswith("."):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"evidence for {key}\n", encoding="utf-8")
            else:
                path.mkdir(parents=True, exist_ok=True)
                (path / ".keep").write_text("evidence\n", encoding="utf-8")


def test_starter_template_contract_is_valid() -> None:
    assert contract_findings(_template()) == []


def test_complete_repository_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_mcp_declaration_is_optional() -> None:
    data = _template()
    data["interfaces"].pop("mcp")

    assert contract_findings(data) == []


def test_mcp_evidence_is_required_only_when_enabled() -> None:
    data = _template()
    data["interfaces"]["mcp"] = False
    assert "mcp" not in required_evidence_keys(data)

    data["interfaces"]["mcp"] = True
    assert "mcp" in required_evidence_keys(data)


def test_agent_tool_accepts_plugin_without_mcp_declaration() -> None:
    data = _template()
    data["product"]["profile"] = "agent-tool"
    data["plugin"]["enabled"] = True
    data["interfaces"]["plugin"] = True
    data["interfaces"].pop("mcp")

    assert contract_findings(data) == []


def test_security_scan_requires_generic_security_evidence() -> None:
    keys = required_evidence_keys(_template())

    assert "security_evidence" in keys
    assert "security_workflow" not in keys


def test_workflow_security_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    data["evidence"]["paths"]["security_evidence"] = ".github/workflows/codeql.yml"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_native_ruleset_security_evidence_passes(tmp_path: Path) -> None:
    data = _template()
    data["evidence"]["paths"]["security_evidence"] = ".github/SECURITY_ENFORCEMENT.md"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)

    _, findings = validate_manifest(manifest, tmp_path)

    assert findings == []


def test_legacy_security_workflow_key_is_not_an_alias(tmp_path: Path) -> None:
    data = _template()
    _materialize_evidence(tmp_path, data)
    data["evidence"]["paths"].pop("security_evidence")
    data["evidence"]["paths"]["security_workflow"] = ".github/SECURITY_ENFORCEMENT.md"
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.declaration_missing"
        and finding.path == "evidence.paths.security_evidence"
        for finding in findings
    )


def test_unknown_controlled_field_is_rejected() -> None:
    data = _template()
    data["product"]["unexpected"] = True

    findings = contract_findings(data)

    assert any(finding.code == "schema.invalid" for finding in findings)


def test_floating_standard_ref_is_rejected() -> None:
    data = _template()
    data["standard"]["ref"] = "main"

    findings = contract_findings(data)

    assert any(finding.code == "standard.ref_not_immutable" for finding in findings)


def test_plugin_profile_requires_plugin_evidence(tmp_path: Path) -> None:
    data = copy.deepcopy(_template())
    data["product"]["profile"] = "plugin"
    data["plugin"]["enabled"] = True
    data["plugin"]["codex"] = {"supported": True, "marketplace": True}
    data["plugin"]["discovery"] = {
        "entry_points": True,
        "manifest": True,
        "capabilities": True,
    }
    data["interfaces"].update({"sdk": False, "plugin": True})
    data["evidence"]["paths"].update(
        {
            "plugin_manifest": ".codex-plugin/plugin.json",
            "plugin_tests": "tests/test_plugin.py",
        }
    )
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _materialize_evidence(tmp_path, data)
    (tmp_path / ".codex-plugin/plugin.json").unlink()

    _, findings = validate_manifest(manifest, tmp_path)

    assert any(
        finding.code == "evidence.path_missing" and finding.path == "evidence.paths.plugin_manifest"
        for finding in findings
    )


def test_init_copies_canonical_template(tmp_path: Path) -> None:
    class Args:
        destination = str(tmp_path / "AI_NATIVE_PLATFORM.yaml")
        force = False

    assert command_init(Args()) == 0
    assert load_mapping(Path(Args.destination))["version"] == 1
