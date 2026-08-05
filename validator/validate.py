"""Validate a product against the canonical AI-native platform contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

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


def validate(data: dict[str, Any], root: Path) -> list[str]:
    """Return validation errors for one product manifest."""
    errors: list[str] = []
    if data.get("version") != 1:
        errors.append("version must be 1")

    standard = data.get("standard", {})
    if standard.get("repository") != "fatmambot33/ai-native-platform":
        errors.append("standard.repository must be fatmambot33/ai-native-platform")
    if not standard.get("ref"):
        errors.append("standard.ref must pin a release tag or commit")

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

    required_files = (
        ".github/ISSUE_TEMPLATE/ai-improvement.yml",
        ".github/workflows/ai-self-improve.yml",
    )
    for relative in required_files:
        if not (root / relative).is_file():
            errors.append(f"missing required repository file: {relative}")

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

    print("AI-native platform validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
