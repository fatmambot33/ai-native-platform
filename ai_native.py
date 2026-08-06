"""AI-native platform conformance validation and command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import sysconfig
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

STANDARD_REPOSITORY = "fatmambot33/ai-native-platform"
SCHEMA_NAME = "ai-native-platform.schema.json"
TEMPLATE_NAME = "AI_NATIVE_PLATFORM.yaml"
REF_PATTERN = re.compile(r"(?:[0-9a-f]{40}|v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
REQUIRED_AGENT_GUARANTEES = {
    "deterministic_tool_discovery",
    "structured_outputs",
    "issue_driven_improvement",
    "ci_validated_changes",
    "governed_autonomy",
}
PROFILE_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "library": ("interfaces.sdk", "interfaces.json_schema"),
    "cli": ("interfaces.cli", "interfaces.json_schema"),
    "plugin": ("interfaces.plugin", "plugin.enabled", "interfaces.json_schema"),
    "agent-tool": ("interfaces.json_schema",),
    "service": ("interfaces.json_schema",),
    "full-platform": (
        "interfaces.sdk",
        "interfaces.cli",
        "interfaces.plugin",
        "plugin.enabled",
        "interfaces.json_schema",
    ),
}
BASE_EVIDENCE = {
    "readme",
    "tests",
    "agent_instructions",
    "typing",
    "ci",
}


@dataclass(frozen=True)
class Finding:
    """One conformance finding."""

    code: str
    message: str
    path: str | None = None

    def render(self) -> str:
        """Return a human-readable finding."""
        location = f" [{self.path}]" if self.path else ""
        return f"{self.code}{location}: {self.message}"


def _repository_root() -> Path:
    """Return the source checkout root when running from this repository."""
    return Path(__file__).resolve().parent


def _data_root() -> Path:
    """Return the installed shared-data root."""
    return Path(sysconfig.get_path("data")) / "share" / "ai-native-platform"


def schema_path() -> Path:
    """Resolve the canonical product manifest schema."""
    override = os.environ.get("AI_NATIVE_PLATFORM_SCHEMA")
    candidates = [
        Path(override) if override else None,
        _repository_root() / "schemas" / SCHEMA_NAME,
        _data_root() / SCHEMA_NAME,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Unable to locate {SCHEMA_NAME}")


def template_path() -> Path:
    """Resolve the canonical starter manifest."""
    override = os.environ.get("AI_NATIVE_PLATFORM_TEMPLATE")
    candidates = [
        Path(override) if override else None,
        _repository_root() / "templates" / TEMPLATE_NAME,
        _data_root() / TEMPLATE_NAME,
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Unable to locate {TEMPLATE_NAME}")


def load_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML or JSON mapping from *path*."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_schema() -> dict[str, Any]:
    """Read and validate the canonical JSON Schema."""
    data = json.loads(schema_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Manifest schema must contain a JSON object")
    Draft202012Validator.check_schema(data)
    return data


def read_path(data: Mapping[str, Any], dotted_path: str) -> Any:
    """Read a dotted path from a nested mapping."""
    current: Any = data
    for key in dotted_path.split("."):
        if not isinstance(current, Mapping) or key not in current:
            raise KeyError(dotted_path)
        current = current[key]
    return current


def contract_findings(data: Mapping[str, Any]) -> list[Finding]:
    """Validate schema and semantic product-contract requirements."""
    findings: list[Finding] = []
    schema = load_schema()
    validator = Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or None
        findings.append(Finding("schema.invalid", error.message, path))

    standard = data.get("standard", {})
    if isinstance(standard, Mapping):
        ref = str(standard.get("ref", ""))
        if ref and REF_PATTERN.fullmatch(ref) is None:
            findings.append(
                Finding(
                    "standard.ref_not_immutable",
                    "Pin an exact semantic version such as v0.1.0 or a 40-character commit SHA.",
                    "standard.ref",
                )
            )

    product = data.get("product", {})
    profile = product.get("profile") if isinstance(product, Mapping) else None
    if isinstance(profile, str):
        for requirement in PROFILE_REQUIREMENTS.get(profile, ()):
            try:
                if read_path(data, requirement) is not True:
                    findings.append(
                        Finding(
                            "profile.requirement_missing",
                            f"Profile {profile!r} requires this capability to be true.",
                            requirement,
                        )
                    )
            except KeyError:
                findings.append(
                    Finding(
                        "profile.requirement_missing",
                        f"Profile {profile!r} requires this capability.",
                        requirement,
                    )
                )

        interfaces = data.get("interfaces", {})
        if isinstance(interfaces, Mapping):
            if profile == "agent-tool" and not (
                interfaces.get("plugin") is True or interfaces.get("mcp") is True
            ):
                findings.append(
                    Finding(
                        "profile.agent_surface_missing",
                        "The agent-tool profile requires either a plugin or MCP interface.",
                        "interfaces",
                    )
                )
            if profile == "service" and not (
                interfaces.get("openapi") is True or interfaces.get("sdk") is True
            ):
                findings.append(
                    Finding(
                        "profile.service_surface_missing",
                        "The service profile requires an OpenAPI or SDK interface.",
                        "interfaces",
                    )
                )

    agent = data.get("agent", {})
    guarantees = set(agent.get("guarantees", [])) if isinstance(agent, Mapping) else set()
    for guarantee in sorted(REQUIRED_AGENT_GUARANTEES - guarantees):
        findings.append(
            Finding(
                "agent.guarantee_missing",
                f"Required guarantee {guarantee!r} is missing.",
                "agent.guarantees",
            )
        )

    return _deduplicate(findings)


def required_evidence_keys(data: Mapping[str, Any]) -> set[str]:
    """Return evidence keys required by declared capabilities."""
    keys = set(BASE_EVIDENCE)
    interfaces = data.get("interfaces", {})
    quality = data.get("quality", {})
    plugin = data.get("plugin", {})
    self_improvement = data.get("self_improvement", {})

    if isinstance(interfaces, Mapping):
        capability_keys = {
            "sdk": "sdk",
            "cli": "cli",
            "json_schema": "schemas",
            "mcp": "mcp",
            "openapi": "openapi",
        }
        for capability, evidence_key in capability_keys.items():
            if interfaces.get(capability) is True:
                keys.add(evidence_key)
        if interfaces.get("plugin") is True:
            keys.update({"plugin_manifest", "plugin_tests"})

    if isinstance(quality, Mapping):
        if quality.get("docs") is True:
            keys.add("docs")
        if quality.get("examples") is True:
            keys.add("examples")
        if quality.get("security_scan") is True:
            keys.add("security_workflow")

    if isinstance(plugin, Mapping):
        credentials = plugin.get("credentials", {})
        if isinstance(credentials, Mapping) and credentials.get("required") is True:
            keys.update({"env_example", "gitignore"})

    if isinstance(self_improvement, Mapping) and self_improvement.get("enabled") is True:
        keys.update({"self_improvement_workflow", "improvement_issue_template"})

    return keys


def _as_paths(value: Any) -> list[str]:
    """Normalize one evidence path declaration."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item for item in value if isinstance(item, str)]
    return []


def _path_exists(root: Path, declaration: str) -> bool:
    """Return whether a repository-relative path or glob has evidence."""
    if Path(declaration).is_absolute() or ".." in Path(declaration).parts:
        return False
    if any(character in declaration for character in "*?["):
        return any(path.exists() for path in root.glob(declaration))
    return (root / declaration).exists()


def evidence_findings(data: Mapping[str, Any], root: Path) -> list[Finding]:
    """Validate declared repository evidence."""
    findings: list[Finding] = []
    evidence = data.get("evidence", {})
    paths = evidence.get("paths", {}) if isinstance(evidence, Mapping) else {}
    if not isinstance(paths, Mapping):
        return [
            Finding(
                "evidence.paths_invalid",
                "Evidence paths must be a mapping.",
                "evidence.paths",
            )
        ]

    for key in sorted(required_evidence_keys(data)):
        declarations = _as_paths(paths.get(key))
        if not declarations:
            findings.append(
                Finding(
                    "evidence.declaration_missing",
                    f"Declare repository evidence for {key!r}.",
                    f"evidence.paths.{key}",
                )
            )
            continue
        missing = [
            declaration
            for declaration in declarations
            if not _path_exists(root, declaration)
        ]
        if missing:
            findings.append(
                Finding(
                    "evidence.path_missing",
                    "No repository evidence found for: " + ", ".join(missing),
                    f"evidence.paths.{key}",
                )
            )

    return findings


def validate_manifest(
    manifest: Path, root: Path | None = None
) -> tuple[dict[str, Any], list[Finding]]:
    """Validate one product manifest and its repository evidence."""
    data = load_mapping(manifest)
    repository_root = (root or manifest.parent).resolve()
    findings = contract_findings(data)
    if not any(finding.code == "schema.invalid" for finding in findings):
        findings.extend(evidence_findings(data, repository_root))
    return data, _deduplicate(findings)


def conformance_score(findings: Iterable[Finding]) -> int:
    """Return a deterministic high-level conformance score."""
    deductions = {
        "schema.invalid": 20,
        "standard.ref_not_immutable": 15,
        "profile.requirement_missing": 15,
        "profile.agent_surface_missing": 15,
        "profile.service_surface_missing": 15,
        "agent.guarantee_missing": 10,
        "evidence.declaration_missing": 7,
        "evidence.path_missing": 7,
        "evidence.paths_invalid": 20,
    }
    score = 100
    for finding in findings:
        score -= deductions.get(finding.code, 5)
    return max(0, score)


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    """Return stable unique findings."""
    unique: dict[tuple[str, str, str | None], Finding] = {}
    for finding in findings:
        unique[(finding.code, finding.message, finding.path)] = finding
    return list(unique.values())


def _result_payload(manifest: Path, findings: list[Finding]) -> dict[str, Any]:
    """Build a machine-readable result payload."""
    return {
        "manifest": str(manifest),
        "valid": not findings,
        "score": conformance_score(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def _print_result(manifest: Path, findings: list[Finding], as_json: bool) -> None:
    """Print validation output."""
    payload = _result_payload(manifest, findings)
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if findings:
        print(f"AI-native platform validation failed ({payload['score']}/100):")
        for finding in findings:
            print(f"- {finding.render()}")
    else:
        print("AI-native platform validation passed (100/100).")


def command_validate(args: argparse.Namespace) -> int:
    """Run the validate command."""
    manifest = Path(args.manifest)
    try:
        _, findings = validate_manifest(manifest, Path(args.root) if args.root else None)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError, SchemaError) as exc:
        finding = Finding("validator.error", str(exc))
        _print_result(manifest, [finding], args.json)
        return 2
    _print_result(manifest, findings, args.json)
    return 1 if findings else 0


def command_score(args: argparse.Namespace) -> int:
    """Run the score command."""
    manifest = Path(args.manifest)
    try:
        _, findings = validate_manifest(manifest, Path(args.root) if args.root else None)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError, SchemaError) as exc:
        findings = [Finding("validator.error", str(exc))]
    payload = _result_payload(manifest, findings)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Conformance score: {payload['score']}/100")
        print(f"Status: {'passing' if payload['valid'] else 'failing'}")
        print(f"Findings: {len(findings)}")
    return 1 if findings else 0


def command_doctor(args: argparse.Namespace) -> int:
    """Check validator installation and repository prerequisites."""
    checks: list[tuple[str, bool, str]] = []
    checks.append(("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0]))
    try:
        resolved_schema = schema_path()
        load_schema()
        checks.append(("JSON Schema", True, str(resolved_schema)))
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as exc:
        checks.append(("JSON Schema", False, str(exc)))
    try:
        resolved_template = template_path()
        checks.append(("Starter template", True, str(resolved_template)))
    except OSError as exc:
        checks.append(("Starter template", False, str(exc)))

    manifest = Path(args.manifest)
    if manifest.exists():
        try:
            _, findings = validate_manifest(manifest, Path(args.root) if args.root else None)
            checks.append(("Repository manifest", not findings, f"{len(findings)} finding(s)"))
        except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError, SchemaError) as exc:
            checks.append(("Repository manifest", False, str(exc)))
    else:
        checks.append(("Repository manifest", False, f"not found: {manifest}"))

    failed = False
    for label, passed, detail in checks:
        failed = failed or not passed
        print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
    return 1 if failed else 0


def command_init(args: argparse.Namespace) -> int:
    """Create a starter product manifest."""
    destination = Path(args.destination)
    if destination.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {destination}", file=sys.stderr)
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path(), destination)
    print(f"Created {destination}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(prog="ai-native")
    parser.add_argument("--version", action="version", version="ai-native-platform 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a repository manifest and evidence"
    )
    validate_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    validate_parser.add_argument("--root")
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.set_defaults(handler=command_validate)

    score_parser = subparsers.add_parser("score", help="Report a deterministic conformance score")
    score_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    score_parser.add_argument("--root")
    score_parser.add_argument("--json", action="store_true")
    score_parser.set_defaults(handler=command_score)

    doctor_parser = subparsers.add_parser(
        "doctor", help="Check installation and repository readiness"
    )
    doctor_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    doctor_parser.add_argument("--root")
    doctor_parser.set_defaults(handler=command_doctor)

    init_parser = subparsers.add_parser("init", help="Create a starter manifest")
    init_parser.add_argument("destination", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(handler=command_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the AI-native platform CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
