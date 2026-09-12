"""Additional contract regression coverage for manifest v1."""

from ai_native import contract_findings, load_mapping, template_path


def test_manifest_v1_skills_failure_is_schema_scoped() -> None:
    """The version-scoped rejection should be reported as a schema error."""
    data = load_mapping(template_path())
    data["version"] = 1
    data["standard"]["ref"] = "v0.2.0"

    findings = contract_findings(data)

    assert any(
        finding.code == "schema.invalid" and finding.path == "agent"
        for finding in findings
    )
