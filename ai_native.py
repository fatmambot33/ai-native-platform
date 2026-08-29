"""AI-native platform conformance validation and command-line interface."""

from __future__ import annotations

import argparse
import copy
import difflib
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

__version__ = "0.2.0"
STANDARD_REPOSITORY = "fatmambot33/ai-native-platform"
SCHEMA_NAME = "ai-native-platform.schema.json"
TEMPLATE_NAME = "AI_NATIVE_PLATFORM.yaml"
CURRENT_MANIFEST_VERSION = 1
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
BASE_EVIDENCE = {"readme", "tests", "agent_instructions", "typing", "ci"}
AI_REVIEW_ACTION = "fatmambot33/ai-native-platform/actions/codex-review-gate"
TRUSTED_AI_REVIEW_GATE_REFS = frozenset(
    {
        "e1eb223d546407310b7a1aaeae2b7a703155434d",
    }
)


@dataclass(frozen=True)
class Finding:
    """One conformance finding."""

    code: str
    message: str
    path: str | None = None
    level: str = "error"

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


def dump_mapping(data: Mapping[str, Any]) -> str:
    """Serialize a manifest deterministically."""
    return yaml.safe_dump(
        dict(data),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


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
    validator = Draft202012Validator(load_schema())
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
                    "Pin an exact semantic version or a 40-character commit SHA.",
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
            keys.add("security_evidence")

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
    path = Path(declaration)
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(character in declaration for character in "*?["):
        return any(candidate.exists() for candidate in root.glob(declaration))
    return (root / declaration).exists()


def _workflow_events(workflow: Mapping[Any, Any]) -> set[str]:
    """Return GitHub workflow event names despite PyYAML's YAML 1.1 `on` coercion."""
    events = workflow.get("on")
    if events is None and True in workflow:
        events = workflow.get(True)
    if isinstance(events, str):
        return {events}
    if isinstance(events, Mapping):
        return {str(key) for key in events}
    if isinstance(events, Sequence) and not isinstance(events, (str, bytes)):
        return {str(item) for item in events}
    return set()


def _job_permissions(job: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a job permission mapping or an empty mapping."""
    permissions = job.get("permissions", {})
    return permissions if isinstance(permissions, Mapping) else {}


def _uses_event(job: Mapping[str, Any], event_name: str) -> bool:
    """Return whether a job condition binds execution to one GitHub event."""
    condition = job.get("if")
    return isinstance(condition, str) and f"github.event_name == '{event_name}'" in condition


def _gate_ref(job: Mapping[str, Any], mode: str) -> str | None:
    """Return the canonical gate ref used by a request or wait job."""
    steps = job.get("steps", [])
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        return None
    prefix = f"{AI_REVIEW_ACTION}@"
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        uses = step.get("uses")
        inputs = step.get("with", {})
        if not isinstance(uses, str) or not uses.startswith(prefix) or not isinstance(inputs, Mapping):
            continue
        if inputs.get("mode") != mode:
            continue
        if inputs.get("pr-number") != "${{ github.event.pull_request.number }}":
            continue
        if inputs.get("head-sha") != "${{ github.event.pull_request.head.sha }}":
            continue
        return uses[len(prefix) :]
    return None


def _has_forbidden_write_permissions(value: Any) -> bool:
    """Return whether parsed workflow data grants writable status or check APIs."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in {"statuses", "checks"} and str(item).lower() == "write":
                return True
            if _has_forbidden_write_permissions(item):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_has_forbidden_write_permissions(item) for item in value)
    return False


def _single_ai_review_workflow_findings(value: str, root: Path) -> list[Finding]:
    """Validate one explicitly declared trusted AI-review workflow."""
    path_name = "evidence.paths.ai_review_workflow"
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) < 3
        or relative.parts[0:2] != (".github", "workflows")
        or relative.suffix not in {".yml", ".yaml"}
    ):
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                "AI review evidence must point to a .github/workflows YAML file.",
                path_name,
            )
        ]

    workflow_path = root / relative
    if not workflow_path.is_file():
        return [
            Finding(
                "evidence.path_missing",
                f"No repository evidence found for: {value}",
                path_name,
            )
        ]

    try:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                f"AI review workflow YAML is invalid: {exc}",
                path_name,
            )
        ]
    if not isinstance(workflow, Mapping):
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                "AI review workflow must contain a YAML mapping.",
                path_name,
            )
        ]

    failures: list[str] = []
    events = _workflow_events(workflow)
    for event_name in ("pull_request", "pull_request_target"):
        if event_name not in events:
            failures.append(f"missing {event_name} event")

    jobs = workflow.get("jobs", {})
    if not isinstance(jobs, Mapping):
        failures.append("jobs must be a mapping")
        jobs = {}
    request = jobs.get("request", {})
    wait = jobs.get("codex-review", {})
    if not isinstance(request, Mapping):
        failures.append("request job is missing")
        request = {}
    if not isinstance(wait, Mapping):
        failures.append("codex-review job is missing")
        wait = {}

    if not _uses_event(request, "pull_request_target"):
        failures.append("request job is not bound to pull_request_target")
    if not _uses_event(wait, "pull_request"):
        failures.append("codex-review job is not bound to pull_request")

    request_permissions = _job_permissions(request)
    if request_permissions.get("issues") != "write":
        failures.append("request job must grant issues: write")
    if request_permissions.get("pull-requests") != "read":
        failures.append("request job must grant pull-requests: read")
    wait_permissions = _job_permissions(wait)
    if wait_permissions.get("issues") != "read":
        failures.append("codex-review job must grant issues: read")
    if wait_permissions.get("pull-requests") != "read":
        failures.append("codex-review job must grant pull-requests: read")
    if any(str(permission).lower() == "write" for permission in wait_permissions.values()):
        failures.append("codex-review job must remain read-only")

    concurrency = workflow.get("concurrency", {})
    if not isinstance(concurrency, Mapping) or concurrency.get("cancel-in-progress") is not True:
        failures.append("concurrency must cancel superseded runs")
    elif "github.event.pull_request.number" not in str(concurrency.get("group", "")):
        failures.append("concurrency must be scoped to the pull request")

    request_ref = _gate_ref(request, "request")
    wait_ref = _gate_ref(wait, "wait")
    for label, reference in (("request", request_ref), ("wait", wait_ref)):
        if reference is None:
            failures.append(f"{label} job must invoke the canonical gate with current PR inputs")
        elif reference not in TRUSTED_AI_REVIEW_GATE_REFS:
            failures.append(f"{label} job uses an untrusted gate revision {reference}")
    if request_ref is not None and wait_ref is not None and request_ref != wait_ref:
        failures.append("request and wait jobs must pin the same gate revision")

    if _has_forbidden_write_permissions(workflow):
        failures.append("workflow must not grant statuses: write or checks: write")

    if failures:
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                "AI review workflow is missing trusted governance semantics: "
                + "; ".join(failures),
                path_name,
            )
        ]
    return []


def _ai_review_workflow_findings(value: Any, root: Path) -> list[Finding]:
    """Validate every explicitly declared trusted AI-review workflow."""
    path_name = "evidence.paths.ai_review_workflow"
    declarations = _as_paths(value)
    expected = 1 if isinstance(value, str) else len(value) if isinstance(value, Sequence) else 0
    if not declarations or len(declarations) != expected:
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                "AI review evidence must be a workflow path string or a nonempty list of strings.",
                path_name,
            )
        ]

    findings: list[Finding] = []
    for declaration in declarations:
        findings.extend(_single_ai_review_workflow_findings(declaration, root))
    return findings


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
        missing = [declaration for declaration in declarations if not _path_exists(root, declaration)]
        if missing:
            findings.append(
                Finding(
                    "evidence.path_missing",
                    "No repository evidence found for: " + ", ".join(missing),
                    f"evidence.paths.{key}",
                )
            )

    if "ai_review_workflow" in paths:
        findings.extend(_ai_review_workflow_findings(paths["ai_review_workflow"], root))
    return findings


def validate_manifest(
    manifest: Path,
    root: Path | None = None,
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
        "evidence.ai_review_workflow_invalid": 20,
    }
    return max(0, 100 - sum(deductions.get(item.code, 5) for item in findings))


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    """Return stable unique findings."""
    unique: dict[tuple[str, str, str | None, str], Finding] = {}
    for finding in findings:
        unique[(finding.code, finding.message, finding.path, finding.level)] = finding
    return list(unique.values())


def _result_payload(manifest: Path, findings: list[Finding]) -> dict[str, Any]:
    """Build a machine-readable result payload."""
    return {
        "manifest": str(manifest),
        "valid": not findings,
        "score": conformance_score(findings),
        "findings": [asdict(finding) for finding in findings],
    }


def sarif_payload(manifest: Path, findings: Sequence[Finding]) -> dict[str, Any]:
    """Build a SARIF 2.1.0 result document."""
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for finding in findings:
        rules.setdefault(
            finding.code,
            {
                "id": finding.code,
                "name": finding.code.replace(".", "_"),
                "shortDescription": {"text": finding.message},
                "helpUri": (
                    "https://github.com/fatmambot33/ai-native-platform"
                    "/blob/v0.2.0/README.md"
                ),
                "defaultConfiguration": {"level": finding.level},
            },
        )
        result: dict[str, Any] = {
            "ruleId": finding.code,
            "level": finding.level,
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": str(manifest).replace("\\", "/")}
                    }
                }
            ],
        }
        if finding.path:
            result["properties"] = {"manifestPath": finding.path}
        results.append(result)

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ai-native-platform",
                        "version": __version__,
                        "informationUri": "https://github.com/fatmambot33/ai-native-platform",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def _format_result(manifest: Path, findings: list[Finding], output_format: str) -> str:
    """Serialize one validation result."""
    if output_format == "json":
        return json.dumps(_result_payload(manifest, findings), indent=2, sort_keys=True)
    if output_format == "sarif":
        return json.dumps(sarif_payload(manifest, findings), indent=2, sort_keys=True)
    if findings:
        lines = [f"AI-native platform validation failed ({conformance_score(findings)}/100):"]
        lines.extend(f"- {finding.render()}" for finding in findings)
        return "\n".join(lines)
    return "AI-native platform validation passed (100/100)."


def _write_or_print(text: str, output: str | None) -> None:
    """Write text to a file or standard output."""
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def command_validate(args: argparse.Namespace) -> int:
    """Run the validate command."""
    manifest = Path(args.manifest)
    output_format = "json" if args.json else args.format
    try:
        _, findings = validate_manifest(manifest, Path(args.root) if args.root else None)
    except (OSError, ValueError, json.JSONDecodeError, yaml.YAMLError, SchemaError) as exc:
        findings = [Finding("validator.error", str(exc))]
    _write_or_print(_format_result(manifest, findings, output_format), args.output)
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


def _deep_merge(defaults: Mapping[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    """Merge user values over canonical defaults."""
    merged: dict[str, Any] = copy.deepcopy(dict(defaults))
    for key, value in source.items():
        if key in merged and isinstance(merged[key], Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def migrate_manifest(data: Mapping[str, Any]) -> dict[str, Any]:
    """Upgrade a legacy manifest to the current stable contract."""
    source_version = data.get("version", 0)
    if not isinstance(source_version, int):
        raise ValueError("Manifest version must be an integer")
    if source_version > CURRENT_MANIFEST_VERSION:
        raise ValueError(
            f"Manifest version {source_version} is newer than supported "
            f"version {CURRENT_MANIFEST_VERSION}"
        )

    defaults = load_mapping(template_path())
    if source_version < CURRENT_MANIFEST_VERSION:
        migrated = _deep_merge(defaults, data)
    else:
        migrated = copy.deepcopy(dict(data))
    migrated["version"] = CURRENT_MANIFEST_VERSION

    migrated_security_key = False
    evidence = migrated.get("evidence", {})
    paths = evidence.get("paths", {}) if isinstance(evidence, Mapping) else {}
    if isinstance(paths, dict) and "security_workflow" in paths:
        if "security_evidence" not in paths:
            paths["security_evidence"] = paths["security_workflow"]
        del paths["security_workflow"]
        migrated_security_key = True

    standard = migrated.setdefault("standard", {})
    if isinstance(standard, dict):
        reference = str(standard.get("ref", ""))
        standard["repository"] = STANDARD_REPOSITORY
        if (
            source_version < CURRENT_MANIFEST_VERSION
            or migrated_security_key
            or reference == "v0.1.0"
        ):
            standard["ref"] = f"v{__version__}"
        else:
            standard.setdefault("ref", f"v{__version__}")
    return migrated


def command_upgrade(args: argparse.Namespace) -> int:
    """Upgrade a manifest with dry-run and diff support."""
    source = Path(args.manifest)
    try:
        original = load_mapping(source)
        upgraded = migrate_manifest(original)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"Upgrade failed: {exc}", file=sys.stderr)
        return 2

    old_text = source.read_text(encoding="utf-8")
    new_text = dump_mapping(upgraded)
    if args.diff or args.dry_run:
        diff = difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile=str(source),
            tofile=str(args.output or source),
            lineterm="",
        )
        print("\n".join(diff) or "Manifest is already current.")
    if args.dry_run:
        return 0

    destination = Path(args.output) if args.output else source
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(new_text, encoding="utf-8")
    print(f"Upgraded {source} to manifest version {CURRENT_MANIFEST_VERSION}.")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    """Check validator installation and repository prerequisites."""
    checks: list[tuple[str, bool, str]] = [
        ("Python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
    ]
    try:
        resolved_schema = schema_path()
        load_schema()
        checks.append(("JSON Schema", True, str(resolved_schema)))
    except (OSError, ValueError, json.JSONDecodeError, SchemaError) as exc:
        checks.append(("JSON Schema", False, str(exc)))
    try:
        checks.append(("Starter template", True, str(template_path())))
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

    for label, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
    return 1 if any(not passed for _, passed, _ in checks) else 0


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
    parser.add_argument(
        "--version",
        action="version",
        version=f"ai-native-platform {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a repository manifest and evidence",
    )
    validate_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    validate_parser.add_argument("--root")
    validate_parser.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    validate_parser.add_argument("--json", action="store_true")
    validate_parser.add_argument("--output")
    validate_parser.set_defaults(handler=command_validate)

    score_parser = subparsers.add_parser(
        "score",
        help="Report a deterministic conformance score",
    )
    score_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    score_parser.add_argument("--root")
    score_parser.add_argument("--json", action="store_true")
    score_parser.set_defaults(handler=command_score)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check installation and repository readiness",
    )
    doctor_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    doctor_parser.add_argument("--root")
    doctor_parser.set_defaults(handler=command_doctor)

    init_parser = subparsers.add_parser("init", help="Create a starter manifest")
    init_parser.add_argument("destination", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(handler=command_init)

    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="Upgrade a legacy manifest to the current contract",
    )
    upgrade_parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    upgrade_parser.add_argument("--output")
    upgrade_parser.add_argument("--dry-run", action="store_true")
    upgrade_parser.add_argument("--diff", action="store_true")
    upgrade_parser.set_defaults(handler=command_upgrade)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the AI-native platform CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())