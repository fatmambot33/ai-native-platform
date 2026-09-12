"""Regression coverage for version-scoped agent skills."""

from ai_native import contract_findings, load_mapping, template_path


def test_manifest_v1_rejects_v2_agent_skills() -> None:
    """Manifest v1 must not claim the v2-only agent skills block."""
    data = load_mapping(template_path())
    data["version"] = 1
    data["standard"]["ref"] = "v0.2.0"

    findings = contract_findings(data)

    assert any(finding.code == "schema.invalid" for finding in findings)
