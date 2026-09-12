"""Manifest v1 compatibility guard."""

from ai_native import contract_findings, load_mapping, template_path


def test_manifest_v1_with_skills_is_invalid() -> None:
    """Version 1 cannot opt into the version-2 skills block."""
    data = load_mapping(template_path())
    data["version"] = 1
    data["standard"]["ref"] = "v0.2.0"

    assert any(item.code == "schema.invalid" for item in contract_findings(data))
