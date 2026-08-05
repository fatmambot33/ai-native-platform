"""Validate the canonical AI-native platform standard repository."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(".")
STANDARD_FILE = ROOT / "standard/AI_NATIVE_PLATFORM.yaml"
SCHEMA_FILE = ROOT / "schemas/ai-native-platform.schema.json"
CHECKLIST_FILE = ROOT / "CHECKLIST.md"
STANDARD_REPOSITORY = "fatmambot33/ai-native-platform"

REQUIRED_FILES = (
    Path("README.md"),
    Path("CHECKLIST.md"),
    Path("standard/AI_NATIVE_PLATFORM.yaml"),
    Path("schemas/ai-native-platform.schema.json"),
    Path("validator/validate.py"),
    Path("validator/validate_standard.py"),
    Path("docs/GOVERNANCE.md"),
    Path(".github/ISSUE_TEMPLATE/ai-improvement.yml"),
    Path(".github/workflows/self-improve.yml"),
)

REQUIRED_CHECKLIST_HEADINGS = (
    "## Vision & Product",
    "## AI Contracts",
    "## Agent Readiness",
    "## SDKs",
    "## APIs",
    "## Documentation",
    "## Developer Experience",
    "## Reliability",
    "## Observability",
    "## Security",
    "## AI Evaluation",
    "## Testing",
    "## Automation",
    "## CI/CD",
    "## Distribution",
    "## Community",
    "## Self-Improvement",
    "## AI-Native Excellence",
    "## Definition of Done",
)

REQUIRED_AGENT_GUARANTEES = {
    "deterministic_tool_discovery",
    "structured_outputs",
    "issue_driven_improvement",
    "ci_validated_changes",
    "governed_autonomy",
}


def _read_mapping(path: Path) -> dict[str, Any]:
    """Read one YAML mapping."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def validate_standard() -> list[str]:
    """Return canonical standard validation errors."""
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing canonical file: {relative}")

    if errors:
        return errors

    standard = _read_mapping(STANDARD_FILE)
    if standard.get("version") != 1:
        errors.append("standard version must be 1")

    identity = standard.get("standard", {})
    if not isinstance(identity, dict):
        errors.append("standard.standard must be a mapping")
    else:
        if identity.get("repository") != STANDARD_REPOSITORY:
            errors.append(f"standard.repository must be {STANDARD_REPOSITORY}")
        if identity.get("versioning") != "semver":
            errors.append("standard.versioning must be semver")

    requirements = standard.get("requirements", {})
    if not isinstance(requirements, dict):
        errors.append("requirements must be a mapping")
    else:
        for section in (
            "product",
            "plugin",
            "credentials",
            "interfaces",
            "quality",
            "self_improvement",
            "governance",
        ):
            if not isinstance(requirements.get(section), dict):
                errors.append(f"requirements.{section} must be a mapping")

        product = requirements.get("product", {})
        for key in ("ai_native", "plugin_first", "typed", "structured_outputs"):
            if product.get(key) is not True:
                errors.append(f"requirements.product.{key} must be true")

        plugin = requirements.get("plugin", {})
        for key in (
            "manifest",
            "codex_support",
            "marketplace_support",
            "deterministic_discovery",
            "capability_metadata",
        ):
            if plugin.get(key) is not True:
                errors.append(f"requirements.plugin.{key} must be true")

    guarantees = set(standard.get("required_agent_guarantees", []))
    missing_guarantees = REQUIRED_AGENT_GUARANTEES - guarantees
    if missing_guarantees:
        errors.append(
            "missing required agent guarantees: "
            + ", ".join(sorted(missing_guarantees))
        )

    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        errors.append("manifest schema must use JSON Schema draft 2020-12")
    required_manifest_fields = {
        "version",
        "standard",
        "product",
        "plugin",
        "interfaces",
        "quality",
        "release",
        "agent",
        "self_improvement",
    }
    missing_schema_fields = required_manifest_fields - set(schema.get("required", []))
    if missing_schema_fields:
        errors.append(
            "manifest schema missing required fields: "
            + ", ".join(sorted(missing_schema_fields))
        )

    checklist = CHECKLIST_FILE.read_text(encoding="utf-8")
    for heading in REQUIRED_CHECKLIST_HEADINGS:
        if heading not in checklist:
            errors.append(f"checklist missing heading: {heading}")

    definition = checklist.split("## Definition of Done", maxsplit=1)
    if len(definition) != 2 or "Every capability is defined once" not in definition[1]:
        errors.append("checklist Definition of Done is incomplete")

    return errors


def main() -> int:
    """Run canonical standard self-validation."""
    try:
        errors = validate_standard()
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Canonical AI-native standard validation failed: {exc}")
        return 1

    if errors:
        print("Canonical AI-native standard validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Canonical AI-native standard validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
