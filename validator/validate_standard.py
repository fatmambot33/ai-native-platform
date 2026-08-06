"""Validate the canonical AI-native platform standard repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_native import (  # noqa: E402
    Finding,
    STANDARD_REPOSITORY,
    contract_findings,
    load_mapping,
    load_schema,
)

STANDARD_FILE = ROOT / "standard/AI_NATIVE_PLATFORM.yaml"
CHECKLIST_FILE = ROOT / "CHECKLIST.md"
TEMPLATE_FILE = ROOT / "templates/AI_NATIVE_PLATFORM.yaml"
ISSUE_FORM = ROOT / ".github/ISSUE_TEMPLATE/ai-improvement.yml"

REQUIRED_FILES = (
    "README.md",
    "CHECKLIST.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "pyproject.toml",
    "ai_native.py",
    "standard/AI_NATIVE_PLATFORM.yaml",
    "schemas/ai-native-platform.schema.json",
    "validator/validate.py",
    "validator/validate_standard.py",
    "templates/AI_NATIVE_PLATFORM.yaml",
    "templates/validate.yml",
    "templates/AGENTS.md",
    "docs/GOVERNANCE.md",
    "tests/test_validation.py",
    "tests/test_standard.py",
    ".github/ISSUE_TEMPLATE/ai-improvement.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/workflows/validate.yml",
    ".github/workflows/quality.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/self-improve.yml",
)

REQUIRED_CHECKLIST_HEADINGS = (
    "## Vision & Product",
    "## AI Contracts",
    "## Plugin Surface",
    "## Agent Readiness",
    "## SDKs",
    "## APIs",
    "## Typing & Schemas",
    "## Installation & Configuration",
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

EXPECTED_PROFILES = {"library", "cli", "service", "agent-tool", "plugin", "full-platform"}


def validate_standard(root: Path = ROOT) -> list[Finding]:
    """Return canonical standard validation findings."""
    findings: list[Finding] = []

    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            findings.append(
                Finding(
                    "standard.file_missing",
                    "Required canonical file is missing.",
                    relative,
                )
            )

    if findings:
        return findings

    standard = load_mapping(root / "standard/AI_NATIVE_PLATFORM.yaml")
    if standard.get("version") != 1:
        findings.append(
            Finding("standard.version_invalid", "Standard version must be 1.", "version")
        )

    identity = standard.get("standard", {})
    if not isinstance(identity, dict):
        findings.append(
            Finding("standard.identity_invalid", "standard must be a mapping.", "standard")
        )
    else:
        if identity.get("repository") != STANDARD_REPOSITORY:
            findings.append(
                Finding(
                    "standard.repository_invalid",
                    f"Repository must be {STANDARD_REPOSITORY}.",
                    "standard.repository",
                )
            )
        if identity.get("versioning") != "semver":
            findings.append(
                Finding(
                    "standard.versioning_invalid",
                    "Versioning must be semver.",
                    "standard.versioning",
                )
            )
        release = str(identity.get("current_release", ""))
        if re.fullmatch(r"\d+\.\d+\.\d+", release) is None:
            findings.append(
                Finding(
                    "standard.release_invalid",
                    "current_release must be an exact semantic version.",
                    "standard.current_release",
                )
            )

    profiles = standard.get("profiles", {})
    if not isinstance(profiles, dict):
        findings.append(
            Finding("standard.profiles_invalid", "profiles must be a mapping.", "profiles")
        )
    else:
        missing_profiles = EXPECTED_PROFILES - set(profiles)
        for profile in sorted(missing_profiles):
            findings.append(
                Finding(
                    "standard.profile_missing",
                    f"Required profile {profile!r} is missing.",
                    "profiles",
                )
            )

    try:
        schema = load_schema()
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as exc:
        findings.append(
            Finding(
                "standard.schema_invalid",
                str(exc),
                "schemas/ai-native-platform.schema.json",
            )
        )

    template = load_mapping(root / "templates/AI_NATIVE_PLATFORM.yaml")
    for finding in contract_findings(template):
        findings.append(
            Finding(
                "standard.template_invalid",
                finding.render(),
                "templates/AI_NATIVE_PLATFORM.yaml",
            )
        )

    checklist = (root / "CHECKLIST.md").read_text(encoding="utf-8")
    for heading in REQUIRED_CHECKLIST_HEADINGS:
        if heading not in checklist:
            findings.append(Finding("standard.checklist_heading_missing", heading, "CHECKLIST.md"))
    if "Every capability is defined once" not in checklist:
        findings.append(
            Finding(
                "standard.definition_incomplete",
                "Definition of Done must require one canonical capability definition.",
                "CHECKLIST.md",
            )
        )

    issue_form = yaml.safe_load(
        (root / ".github/ISSUE_TEMPLATE/ai-improvement.yml").read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(issue_form, dict):
        findings.append(
            Finding(
                "standard.issue_form_invalid",
                "Issue form must be a mapping.",
                str(ISSUE_FORM),
            )
        )
    else:
        for key in ("name", "description", "body"):
            if not issue_form.get(key):
                findings.append(
                    Finding(
                        "standard.issue_form_key_missing",
                        f"Issue form requires {key!r}.",
                        str(ISSUE_FORM),
                    )
                )
        if "about" in issue_form:
            findings.append(
                Finding(
                    "standard.issue_form_legacy_key",
                    "YAML issue forms use description, not about.",
                    str(ISSUE_FORM),
                )
            )
        labels = issue_form.get("labels", [])
        if labels != ["enhancement"]:
            findings.append(
                Finding(
                    "standard.issue_form_label_invalid",
                    "Use the built-in enhancement label until managed labels are provisioned.",
                    str(ISSUE_FORM),
                )
            )

    validator_source = (root / "ai_native.py").read_text(encoding="utf-8")
    if "Draft202012Validator" not in validator_source:
        findings.append(
            Finding(
                "standard.schema_not_enforced",
                "The product validator must execute JSON Schema validation.",
                "ai_native.py",
            )
        )

    readme = (root / "README.md").read_text(encoding="utf-8")
    if re.search(r"uses:\s+[^\s]+@main(?:\s|$)", readme):
        findings.append(
            Finding(
                "standard.floating_reference",
                "Production documentation must not recommend @main.",
                "README.md",
            )
        )

    return _deduplicate(findings)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Return stable unique findings."""
    unique: dict[tuple[str, str, str | None], Finding] = {}
    for finding in findings:
        unique[(finding.code, finding.message, finding.path)] = finding
    return list(unique.values())


def main(argv: list[str] | None = None) -> int:
    """Run canonical self-validation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        findings = validate_standard()
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError, SchemaError) as exc:
        findings = [Finding("standard.validator_error", str(exc))]

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2, sort_keys=True))
    elif findings:
        print("Canonical AI-native standard validation failed:")
        for finding in findings:
            print(f"- {finding.render()}")
    else:
        print("Canonical AI-native standard validation passed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
