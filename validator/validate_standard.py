"""Validate the canonical AI-native platform standard repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import tomli as tomllib
import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_native import (  # noqa: E402, I001
    STANDARD_REPOSITORY,
    TRUSTED_AI_REVIEW_GATE_REFS,
    Finding,
    contract_findings,
    load_mapping,
    load_schema,
    validate_manifest,
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
    "standard/AI_NATIVE_PLATFORM.yaml",
    "schemas/ai-native-platform.schema.json",
    "validator/validate.py",
    "validator/validate_standard.py",
    "templates/AI_NATIVE_PLATFORM.yaml",
    "templates/validate.yml",
    "templates/AGENTS.md",
    "actions/codex-review-gate/action.yml",
    "actions/codex-review-gate/codex-review-gate.sh",
    "docs/GOVERNANCE.md",
    "docs/AI_REVIEW_GOVERNANCE.md",
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


def _append_contract_findings(root: Path, standard: dict, findings: list[Finding]) -> None:
    """Validate profiles, schema, template, and fixtures."""
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
    if re.search(r"uses:\s+[^\s]+@main(?:\s|$)", readme):
        findings.append(
            Finding(
                "standard.floating_reference",
                "Production documentation must not recommend @main.",
                "README.md",
            )
        )

    codex_review = (root / ".github/workflows/codex-review.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        "pull_request:",
        "pull_request_target:",
        "codex-review:",
        "actions/codex-review-gate",
        "mode: request",
        "mode: wait",
        "issues: write",
        "issues: read",
        "pull-requests: read",
        "github.event_name == 'pull_request_target'",
        "github.event_name == 'pull_request'",
        "cancel-in-progress: true",
    ):
        if token not in codex_review:
            findings.append(
                Finding(
                    "standard.ai_review_workflow_incomplete",
                    f"AI review workflow must include {token!r}.",
                    ".github/workflows/codex-review.yml",
                )
            )
    if re.search(r"(?:statuses|checks):\s*write", codex_review):
        findings.append(
            Finding(
                "standard.ai_review_workflow_unsafe",
                (
                    "AI review workflow must not publish its required result "
                    "through writable status/check APIs."
                ),
                ".github/workflows/codex-review.yml",
            )
        )
    action_refs = re.findall(
        r"uses:\s*fatmambot33/ai-native-platform/actions/codex-review-gate@([0-9a-f]{40})",
        codex_review,
    )
    if not action_refs:
        findings.append(
            Finding(
                "standard.ai_review_action_unpinned",
                "AI review workflow must pin the canonical action to an immutable commit SHA.",
                ".github/workflows/codex-review.yml",
            )
        )
    elif any(reference not in TRUSTED_AI_REVIEW_GATE_REFS for reference in action_refs):
        findings.append(
            Finding(
                "standard.ai_review_action_untrusted",
                "AI review workflow must use a trusted canonical gate revision.",
                ".github/workflows/codex-review.yml",
            )
        )

    codeowners = (root / ".github/CODEOWNERS").read_text(encoding="utf-8")
    for token in (
        "/.github/workflows/** @fatmambot33",
        "/.github/CODEOWNERS @fatmambot33",
        "/actions/codex-review-gate/** @fatmambot33",
        "/schemas/** @fatmambot33",
        "/standard/** @fatmambot33",
        "/ai_native.py @fatmambot33",
        "/validator/** @fatmambot33",
        "/templates/** @fatmambot33",
        "/docs/GOVERNANCE.md @fatmambot33",
        "/pyproject.toml @fatmambot33",
        "/tools/release_artifacts.py @fatmambot33",
    ):
        if token not in codeowners:
            findings.append(
                Finding(
                    "standard.ai_review_codeowners_incomplete",
                    f"Governance CODEOWNERS must include {token!r}.",
                    ".github/CODEOWNERS",
                )
            )

    release_workflow = (root / ".github/workflows/release.yml").read_text(
        encoding="utf-8"
    )
    for token in (
        "actions/attest-build-provenance@v3",
        "python tools/release_artifacts.py dist",
        "gh release create",
        "--verify-tag",
    ):
        if token not in release_workflow:
            findings.append(
                Finding(
                    "standard.release_workflow_incomplete",
                    f"Release workflow must include {token!r}.",
                    ".github/workflows/release.yml",
                )
            )

    self_improve = (root / ".github/workflows/self-improve.yml").read_text(
        encoding="utf-8"
    )
    for token in ("fingerprint", "AI_NATIVE_ISSUE_BUDGET", "issues: write"):
        if token not in self_improve:
            findings.append(
                Finding(
                    "standard.self_improvement_incomplete",
                    f"Self-improvement workflow must include {token!r}.",
                    ".github/workflows/self-improve.yml",
                )
            )


def validate_standard(root: Path = ROOT) -> list[Finding]:
    """Return canonical standard validation findings."""
    findings: list[Finding] = []
    _append_required_file_findings(root, findings)
    if findings:
        return _deduplicate(findings)

    standard = _append_identity_findings(root, findings)
    _append_contract_findings(root, standard, findings)
    _append_repository_findings(root, findings)
    return _deduplicate(findings)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Return stable unique findings."""
    unique: dict[tuple[str, str, str | None, str], Finding] = {}
    for finding in findings:
        unique[(finding.code, finding.message, finding.path, finding.level)] = finding
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
        print(json.dumps([asdict(item) for item in findings], indent=2, sort_keys=True))
    elif findings:
        print("Canonical AI-native standard validation failed:")
        for finding in findings:
            print(f"- {finding.render()}")
    else:
        print("Canonical AI-native standard validation passed.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
