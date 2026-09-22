"""Validate the canonical AI-native platform standard repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import unquote

import tomli as tomllib
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_native import (  # noqa: E402, I001
    STANDARD_REPOSITORY,
    TRUSTED_AI_REVIEW_GATE_REFS,
    Finding,
    _codeowners_effective_owners,
    _single_ai_review_workflow_findings,
    contract_findings,
    load_mapping,
    load_schema,
    validate_manifest,
)
from ai_native_platform.inheritance import (  # noqa: E402
    InheritanceError,
    load_declaration,
    validate_declaration,
)

ISSUE_FORM = ROOT / ".github/ISSUE_TEMPLATE/ai-improvement.yml"
PROFILES = ("library", "cli", "service", "agent-tool", "plugin", "full-platform")
REQUIRED_FILES = (
    "README.md",
    "CHECKLIST.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "RELEASE_NOTES.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "pyproject.toml",
    "ai_native.py",
    "ai_native_entry.py",
    "ai_native_platform/__init__.py",
    "ai_native_platform/inheritance.py",
    "ai_native_platform/schemas/ai-native-derived.schema.json",
    "standard/AI_NATIVE_PLATFORM.yaml",
    "schemas/ai-native-platform.schema.json",
    "schemas/ai-native-derived.schema.json",
    "validator/validate.py",
    "validator/validate_standard.py",
    "templates/AI_NATIVE_PLATFORM.yaml",
    "templates/derived.yaml",
    "templates/validate.yml",
    "templates/AGENTS.md",
    "consumers/registry.yaml",
    "actions/codex-review-gate/action.yml",
    "actions/codex-review-gate/codex-review-gate.sh",
    "docs/GOVERNANCE.md",
    "docs/AI_REVIEW_GOVERNANCE.md",
    "docs/INHERITANCE.md",
    "docs/DISTRIBUTION.md",
    "docs/RELEASE.md",
    "tests/test_validation.py",
    "tests/test_standard.py",
    "tests/test_release_train.py",
    "tools/discover_improvements.py",
    "tools/improvement_engine.py",
    "tools/release_artifacts.py",
    ".ai-native/suppressions.yaml",
    ".ai-native/signals.example.json",
    ".github/ISSUE_TEMPLATE/ai-improvement.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/workflows/validate.yml",
    ".github/workflows/codex-review.yml",
    ".github/workflows/quality.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/self-improve.yml",
    ".github/workflows/release.yml",
    "fixtures/consumer-repository/AI_NATIVE_PLATFORM.yaml",
    "fixtures/consumer-repository/.github/workflows/validate.yml",
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


def _append_required_file_findings(root: Path, findings: list[Finding]) -> None:
    """Require all canonical product surfaces."""
    for relative in REQUIRED_FILES:
        if not (root / relative).exists():
            findings.append(
                Finding(
                    "standard.file_missing",
                    "Required canonical file is missing.",
                    relative,
                )
            )
    if not (root / "fixtures/evidence/README.md").exists():
        findings.append(
            Finding(
                "standard.fixture_evidence_missing",
                "Shared fixture evidence is missing.",
                "fixtures/evidence/README.md",
            )
        )
    for state in ("passing", "failing"):
        for profile in PROFILES:
            relative = f"fixtures/{state}/{profile}.yaml"
            if not (root / relative).exists():
                findings.append(
                    Finding(
                        "standard.fixture_missing",
                        f"Required {state} fixture is missing.",
                        relative,
                    )
                )


def _append_identity_findings(root: Path, findings: list[Finding]) -> dict:
    """Validate canonical identity and aligned release versions."""
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
        return standard

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
        return standard

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(pyproject["project"]["version"])
    template = load_mapping(root / "templates/AI_NATIVE_PLATFORM.yaml")
    template_ref = str(template.get("standard", {}).get("ref", ""))
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    if package_version != release:
        findings.append(
            Finding(
                "standard.package_version_drift",
                f"Package version {package_version} must equal {release}.",
                "pyproject.toml",
            )
        )
    if template_ref != f"v{release}":
        findings.append(
            Finding(
                "standard.template_version_drift",
                f"Starter manifest ref must equal v{release}.",
                "templates/AI_NATIVE_PLATFORM.yaml",
            )
        )
    if f"## [{release}]" not in changelog:
        findings.append(
            Finding(
                "standard.changelog_version_missing",
                f"Changelog must include release {release}.",
                "CHANGELOG.md",
            )
        )
    return standard


def _resolve_local_reference(schema: object, reference: str) -> None:
    """Resolve one local JSON Pointer reference or raise ``ValueError``."""
    if reference == "#":
        return
    if not reference.startswith("#/"):
        raise ValueError(f"Schema reference must be local: {reference!r}")

    target = schema
    for raw_token in reference[2:].split("/"):
        token = unquote(raw_token).replace("~1", "/").replace("~0", "~")
        if isinstance(target, dict) and token in target:
            target = target[token]
            continue
        if isinstance(target, list) and token.isdecimal():
            index = int(token)
            if index < len(target):
                target = target[index]
                continue
        raise ValueError(f"Unresolved local schema reference: {reference!r}")


def _validate_local_references(schema: object, root: object | None = None) -> None:
    """Recursively verify that every schema ``$ref`` resolves locally."""
    root = schema if root is None else root
    if isinstance(schema, dict):
        reference = schema.get("$ref")
        if reference is not None:
            if not isinstance(reference, str):
                raise ValueError("Schema $ref values must be strings")
            _resolve_local_reference(root, reference)
        for value in schema.values():
            _validate_local_references(value, root)
    elif isinstance(schema, list):
        for value in schema:
            _validate_local_references(value, root)


def _append_schema_finding(root: Path, relative: str, findings: list[Finding]) -> None:
    """Parse, meta-validate, and resolve local references in one schema."""
    try:
        schema = json.loads((root / relative).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        _validate_local_references(schema)
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as exc:
        findings.append(Finding("standard.schema_invalid", str(exc), relative))


def _append_packaged_schema_finding(root: Path, findings: list[Finding]) -> None:
    """Require the packaged inheritance schema to match the canonical schema exactly."""
    canonical_relative = "schemas/ai-native-derived.schema.json"
    packaged_relative = "ai_native_platform/schemas/ai-native-derived.schema.json"
    try:
        canonical = (root / canonical_relative).read_bytes()
        packaged = (root / packaged_relative).read_bytes()
    except OSError as exc:
        findings.append(Finding("standard.schema_copy_invalid", str(exc), packaged_relative))
        return
    if packaged != canonical:
        findings.append(
            Finding(
                "standard.schema_copy_drift",
                (
                    "Packaged inheritance schema must be byte-for-byte identical "
                    "to the canonical schema."
                ),
                packaged_relative,
            )
        )


def _append_derived_starter_finding(root: Path, findings: list[Finding]) -> None:
    """Parse and validate the canonical derived-repository starter."""
    relative = "templates/derived.yaml"
    try:
        declaration = load_declaration(root / relative)
        validate_declaration(declaration)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        SchemaError,
        Unresolvable,
        yaml.YAMLError,
        InheritanceError,
        RecursionError,
    ) as exc:
        findings.append(Finding("standard.derived_template_invalid", str(exc), relative))


def _append_contract_findings(root: Path, standard: dict, findings: list[Finding]) -> None:
    """Validate profiles, schemas, template, and fixtures."""
    profiles = standard.get("profiles", {})
    if not isinstance(profiles, dict):
        findings.append(
            Finding("standard.profiles_invalid", "profiles must be a mapping.", "profiles")
        )
    else:
        for profile in sorted(set(PROFILES) - set(profiles)):
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
    _append_schema_finding(root, "schemas/ai-native-derived.schema.json", findings)
    _append_packaged_schema_finding(root, findings)
    _append_derived_starter_finding(root, findings)

    template = load_mapping(root / "templates/AI_NATIVE_PLATFORM.yaml")
    for finding in contract_findings(template):
        findings.append(
            Finding(
                "standard.template_invalid",
                finding.render(),
                "templates/AI_NATIVE_PLATFORM.yaml",
            )
        )

    for profile in PROFILES:
        passing = root / "fixtures" / "passing" / f"{profile}.yaml"
        failing = root / "fixtures" / "failing" / f"{profile}.yaml"
        if passing.is_file():
            _, passing_findings = validate_manifest(passing, root / "fixtures")
            for item in passing_findings:
                findings.append(
                    Finding(
                        "standard.passing_fixture_invalid",
                        item.render(),
                        str(passing.relative_to(root)),
                    )
                )
        if failing.is_file():
            _, failing_findings = validate_manifest(failing, root / "fixtures")
            if not failing_findings:
                findings.append(
                    Finding(
                        "standard.failing_fixture_passed",
                        "Focused failing fixture must produce at least one finding.",
                        str(failing.relative_to(root)),
                    )
                )


def _append_repository_findings(root: Path, findings: list[Finding]) -> None:
    """Validate documentation, issue forms, CLI, and workflow guarantees."""
    checklist = (root / "CHECKLIST.md").read_text(encoding="utf-8")
    for heading in REQUIRED_CHECKLIST_HEADINGS:
        if heading not in checklist:
            findings.append(
                Finding("standard.checklist_heading_missing", heading, "CHECKLIST.md")
            )
    if "Every capability is defined once" not in checklist:
        findings.append(
            Finding(
                "standard.definition_incomplete",
                "Definition of Done must require one canonical capability definition.",
                "CHECKLIST.md",
            )
        )

    issue_form = yaml.safe_load(ISSUE_FORM.read_text(encoding="utf-8"))
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
        if issue_form.get("labels", []) != ["enhancement"]:
            findings.append(
                Finding(
                    "standard.issue_form_label_invalid",
                    "Use the built-in enhancement label until managed labels are provisioned.",
                    str(ISSUE_FORM),
                )
            )

    validator_source = (root / "ai_native.py").read_text(encoding="utf-8")
    for token, code, message in (
        (
            "Draft202012Validator",
            "standard.schema_not_enforced",
            "Product validation must execute JSON Schema.",
        ),
        (
            "sarif_payload",
            "standard.sarif_missing",
            "The CLI must provide SARIF output.",
        ),
        (
            "migrate_manifest",
            "standard.migration_missing",
            "The CLI must provide deterministic manifest migrations.",
        ),
        (
            "_ai_review_workflow_findings",
            "standard.ai_review_semantics_missing",
            "The CLI must semantically validate declared AI-review workflows.",
        ),
    ):
        if token not in validator_source:
            findings.append(Finding(code, message, "ai_native.py"))

    readme = (root / "README.md").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    governance = (root / "docs/GOVERNANCE.md").read_text(encoding="utf-8")
    ai_review_governance = (root / "docs/AI_REVIEW_GOVERNANCE.md").read_text(encoding="utf-8")
    inheritance = (root / "docs/INHERITANCE.md").read_text(encoding="utf-8")
    distribution = (root / "docs/DISTRIBUTION.md").read_text(encoding="utf-8")
    release = (root / "docs/RELEASE.md").read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    codeowners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    pull_request_template = (root / ".github/PULL_REQUEST_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    required_tokens = (
        (readme, "AI Native Platform", "README.md"),
        (changelog, "## [Unreleased]", "CHANGELOG.md"),
        (release_notes, "# Release notes", "RELEASE_NOTES.md"),
        (governance, "Autonomy", "docs/GOVERNANCE.md"),
        (ai_review_governance, "Codex", "docs/AI_REVIEW_GOVERNANCE.md"),
        (inheritance, "Derived", "docs/INHERITANCE.md"),
        (distribution, "PyPI", "docs/DISTRIBUTION.md"),
        (release, "Release", "docs/RELEASE.md"),
        (contributing, "pull request", "CONTRIBUTING.md"),
        (security, "Security", "SECURITY.md"),
        (agents, "Agent Instructions", "AGENTS.md"),
        (codeowners, "@fatmambot33", ".github/CODEOWNERS"),
        (pull_request_template, "Codex", ".github/PULL_REQUEST_TEMPLATE.md"),
    )
    for content, token, path in required_tokens:
        if token not in content:
            findings.append(Finding("standard.documentation_missing", token, path))

    if "ai_native_platform/**" not in codeowners:
        findings.append(
            Finding(
                "standard.codeowners_inheritance_missing",
                "Packaged inheritance runtime must have an explicit CODEOWNERS rule.",
                ".github/CODEOWNERS",
            )
        )
    if "docs/INHERITANCE.md" not in codeowners:
        findings.append(
            Finding(
                "standard.codeowners_inheritance_docs_missing",
                "Inheritance contract documentation must have an explicit CODEOWNERS rule.",
                ".github/CODEOWNERS",
            )
        )

    workflow = (root / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    if "python validator/validate_standard.py" not in workflow:
        findings.append(
            Finding(
                "standard.canonical_validator_not_enforced",
                "Validation workflow must execute canonical repository validation.",
                ".github/workflows/validate.yml",
            )
        )

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject.get("project", {}).get("scripts", {})
    if scripts.get("ai-native") != "ai_native_entry:main":
        findings.append(
            Finding(
                "standard.cli_entrypoint_invalid",
                "ai-native must use the inheritance-aware installed entry point.",
                "pyproject.toml",
            )
        )

    gate_ref = pyproject.get("tool", {}).get("ai-native", {}).get("codex_gate_ref", "")
    if gate_ref not in TRUSTED_AI_REVIEW_GATE_REFS:
        findings.append(
            Finding(
                "standard.codex_gate_ref_invalid",
                "Package metadata must pin a trusted immutable Codex review gate revision.",
                "pyproject.toml",
            )
        )

    for relative in (
        "actions/codex-review-gate/action.yml",
        "actions/codex-review-gate/codex-review-gate.sh",
    ):
        owners = _codeowners_effective_owners(codeowners, relative)
        if "@fatmambot33" not in owners:
            findings.append(
                Finding(
                    "standard.codex_gate_owner_invalid",
                    "Codex review gate implementation must be code-owner protected.",
                    relative,
                )
            )

    registry = load_mapping(root / "consumers/registry.yaml")
    consumers = registry.get("consumers", [])
    if not isinstance(consumers, list):
        findings.append(
            Finding(
                "standard.consumer_registry_invalid",
                "Consumer registry must contain a list of consumers.",
                "consumers/registry.yaml",
            )
        )
        consumers = []
    for index, consumer in enumerate(consumers):
        if not isinstance(consumer, dict):
            findings.append(
                Finding(
                    "standard.consumer_entry_invalid",
                    "Consumer entries must be mappings.",
                    f"consumers[{index}]",
                )
            )
            continue
        if not consumer.get("repository") or not consumer.get("manifest"):
            findings.append(
                Finding(
                    "standard.consumer_entry_incomplete",
                    "Consumer entries require repository and manifest.",
                    f"consumers[{index}]",
                )
            )


def validate_repository(root: Path) -> list[Finding]:
    """Return all canonical repository findings."""
    findings: list[Finding] = []
    _append_required_file_findings(root, findings)
    standard = _append_identity_findings(root, findings)
    _append_contract_findings(root, standard, findings)
    _append_repository_findings(root, findings)
    return findings


def main(argv: list[str] | None = None) -> int:
    """Run canonical repository validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    findings = validate_repository(args.root.resolve())
    if findings:
        for finding in findings:
            print(finding.render())
        return 1
    print("PASS canonical AI-native platform repository")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
