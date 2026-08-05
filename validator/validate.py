"""Validate a product against the canonical AI-native platform contract."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

REQUIRED_TRUE_PATHS = (
    ("product", "ai_native"),
    ("product", "plugin_first"),
    ("plugin", "enabled"),
    ("plugin", "codex", "supported"),
    ("plugin", "codex", "marketplace"),
    ("plugin", "discovery", "entry_points"),
    ("plugin", "discovery", "manifest"),
    ("plugin", "discovery", "capabilities"),
    ("plugin", "credentials", "local_only"),
    ("plugin", "credentials", "policy", "never_store_remote"),
    ("plugin", "credentials", "policy", "never_commit"),
    ("plugin", "credentials", "policy", "never_echo"),
    ("interfaces", "sdk"),
    ("interfaces", "cli"),
    ("interfaces", "plugin"),
    ("interfaces", "json_schema"),
    ("quality", "typed"),
    ("quality", "tests"),
    ("quality", "docs"),
    ("quality", "examples"),
    ("quality", "security_scan"),
    ("release", "block_if_quality_fails"),
    ("release", "block_if_plugin_invalid"),
    ("self_improvement", "enabled"),
    ("self_improvement", "github", "issues"),
    ("self_improvement", "autonomous", "discover_improvements"),
    ("self_improvement", "autonomous", "create_issues"),
    ("self_improvement", "autonomous", "generate_pr"),
    ("self_improvement", "autonomous", "run_ci"),
    ("self_improvement", "governance", "human_approval", "breaking_changes"),
    ("self_improvement", "governance", "human_approval", "security_changes"),
    ("self_improvement", "governance", "human_approval", "credential_changes"),
    ("self_improvement", "governance", "human_approval", "public_api_changes"),
    ("self_improvement", "governance", "human_approval", "release_changes"),
)

REQUIRED_COMMANDS = {"validate", "test", "docs", "examples", "upgrade", "uninstall"}
REQUIRED_GUARANTEES = {
    "deterministic_tool_discovery",
    "structured_outputs",
    "issue_driven_improvement",
    "ci_validated_changes",
    "governed_autonomy",
}


def read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Read a nested manifest value."""
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(".".join(path))
        current = current[key]
    return current


def files(root: Path, patterns: Iterable[str]) -> list[Path]:
    """Return unique files matching repository-relative glob patterns."""
    found: dict[str, Path] = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and ".git" not in path.parts:
                found[str(path)] = path
    return list(found.values())


def contains(paths: Iterable[Path], patterns: Iterable[str]) -> bool:
    """Return whether readable files contain every case-insensitive pattern."""
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in paths
        if path.stat().st_size < 2_000_000
    ).lower()
    return all(pattern.lower() in text for pattern in patterns)


def evidence_errors(root: Path, data: dict[str, Any]) -> list[str]:
    """Validate concrete repository evidence behind manifest declarations."""
    errors: list[str] = []
    readmes = files(root, ("README.md", "docs/**/*.md"))
    python_files = files(root, ("src/**/*.py", "**/plugins/**/*.py", "plugins/**/*.py"))
    workflows = files(root, (".github/workflows/*.yml", ".github/workflows/*.yaml"))
    tests = files(root, ("tests/test_*.py", "tests/**/*test*.py"))

    checks: dict[str, bool] = {
        "packaging metadata (pyproject.toml)": (root / "pyproject.toml").is_file(),
        "Codex plugin manifest": bool(files(root, (".codex-plugin/plugin.json", "plugins/**/.codex-plugin/plugin.json"))),
        "Codex marketplace catalog": bool(files(root, (".agents/plugins/marketplace.json", "plugins/**/marketplace.json"))),
        "typed plugin contract": contains(python_files, ("plugin",)) and (
            contains(python_files, ("protocol",)) or contains(python_files, ("abstractbaseclass",))
        ),
        "typing contract": bool(files(root, ("src/**/py.typed", "**/py.typed")))
        or contains([root / "pyproject.toml"] if (root / "pyproject.toml").is_file() else [], ("pyright",)),
        "strict type checking in CI": contains(workflows, ("pyright",)) or contains(workflows, ("mypy",)),
        "plugin contract tests": bool([path for path in tests if "plugin" in path.name.lower()]),
        "general tests": bool(tests),
        "agent instructions (AGENTS.md)": (root / "AGENTS.md").is_file(),
        "AI improvement issue template": (root / ".github/ISSUE_TEMPLATE/ai-improvement.yml").is_file(),
        "self-improvement workflow": (root / ".github/workflows/ai-self-improvement.yml").is_file()
        or (root / ".github/workflows/ai-self-improve.yml").is_file(),
    }

    if readmes:
        readme_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in readmes).lower()
        checks["PyPI installation documentation"] = "pip install" in readme_text
        checks["Git installation documentation"] = "git+https://" in readme_text or "git clone" in readme_text
        checks["editable installation documentation"] = "pip install -e" in readme_text
        checks["plugin documentation"] = "plugin" in readme_text and ("codex" in readme_text or "entry point" in readme_text)
    else:
        checks.update(
            {
                "README or documentation": False,
                "PyPI installation documentation": False,
                "Git installation documentation": False,
                "editable installation documentation": False,
                "plugin documentation": False,
            }
        )

    credentials = data.get("plugin", {}).get("credentials", {})
    if credentials.get("required"):
        example = credentials.get("env_example")
        checks["credential template"] = isinstance(example, str) and (root / example).is_file()
        checks["configure command declaration"] = bool(credentials.get("setup_command"))
        checks["doctor command declaration"] = bool(credentials.get("validation_command"))
        gitignore = root / ".gitignore"
        checks[".env ignored by Git"] = gitignore.is_file() and ".env" in gitignore.read_text(
            encoding="utf-8", errors="ignore"
        )

    for label, passed in checks.items():
        if not passed:
            errors.append(f"missing repository evidence: {label}")
    return errors


def validate(data: dict[str, Any], root: Path) -> list[str]:
    """Return validation errors for one product manifest and repository."""
    errors: list[str] = []
    if data.get("version") != 1:
        errors.append("version must be 1")

    standard = data.get("standard", {})
    if standard.get("repository") != "fatmambot33/ai-native-platform":
        errors.append("standard.repository must be fatmambot33/ai-native-platform")
    ref = str(standard.get("ref", ""))
    if not re.fullmatch(r"[0-9a-f]{40}|v?\d+\.\d+\.\d+", ref):
        errors.append("standard.ref must pin an immutable commit or semantic version tag")

    for path in REQUIRED_TRUE_PATHS:
        try:
            if read_path(data, path) is not True:
                errors.append(f"{'.'.join(path)} must be true")
        except KeyError:
            errors.append(f"missing {'.'.join(path)}")

    commands = set(data.get("commands", {}).get("required", []))
    for command in sorted(REQUIRED_COMMANDS - commands):
        errors.append(f"commands.required must include {command}")

    credentials = data.get("plugin", {}).get("credentials", {})
    if credentials.get("required"):
        for field in ("env_file", "env_example", "setup_command", "validation_command"):
            if not credentials.get(field):
                errors.append(f"plugin.credentials.{field} is required")
        if not credentials.get("required_variables"):
            errors.append("plugin.credentials.required_variables must not be empty")
        for command in ("configure", "doctor"):
            if command not in commands:
                errors.append(f"credentialed products require command {command}")

    guarantees = set(data.get("agent", {}).get("guarantees", []))
    missing = REQUIRED_GUARANTEES - guarantees
    if missing:
        errors.append("missing agent guarantees: " + ", ".join(sorted(missing)))

    errors.extend(evidence_errors(root, data))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run the validator."""
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default="AI_NATIVE_PLATFORM.yaml")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    manifest = Path(args.manifest)
    root = Path(args.root)
    if not manifest.is_file():
        print(f"Missing manifest: {manifest}", file=sys.stderr)
        return 1

    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("Manifest root must be a mapping", file=sys.stderr)
        return 1

    errors = validate(data, root)
    if errors:
        print("AI-native platform validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("AI-native platform validation passed with repository evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
