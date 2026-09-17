"""Validate and resolve AI Native derived-repository declarations."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

CAPABILITIES = ("welcome", "troubleshooting", "update", "doctor")
PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "python-library": {capability: () for capability in CAPABILITIES}
}
REF_PATTERN = re.compile(r"(?:[0-9a-f]{40}|v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")


class InheritanceError(ValueError):
    """Raised when a derived-repository declaration is unsafe or inconsistent."""


@dataclass(frozen=True)
class ResolvedCapability:
    """One deterministic capability resolution result."""

    name: str
    mode: str
    enabled: bool
    extensions: tuple[str, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True)
class DoctorFinding:
    """One deterministic derived-repository doctor finding."""

    code: str
    message: str
    path: str


def _schema_path() -> Path:
    """Return the canonical inheritance schema path."""
    return Path(__file__).resolve().parents[1] / "schemas" / "ai-native-derived.schema.json"


def load_declaration(path: Path) -> dict[str, Any]:
    """Load a derived-repository YAML declaration."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InheritanceError("derived declaration must contain a mapping")
    return data


def _schema_errors(data: Mapping[str, Any]) -> list[str]:
    """Return stable JSON Schema validation errors."""
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def _safe_path(value: str) -> PurePosixPath:
    """Validate and normalize one repository-relative ownership path."""
    path = PurePosixPath(value)
    if path.is_absolute() or not value or ".." in path.parts or "." in path.parts:
        raise InheritanceError(f"unsafe ownership path: {value!r}")
    return path


def _paths_overlap(left: PurePosixPath, right: PurePosixPath) -> bool:
    """Return whether two ownership paths overlap hierarchically."""
    return left == right or left in right.parents or right in left.parents


def validate_declaration(data: Mapping[str, Any]) -> None:
    """Validate schema plus cross-field inheritance invariants."""
    errors = _schema_errors(data)
    if errors:
        raise InheritanceError("; ".join(errors))

    ref = str(data["platform"]["ref"])
    if REF_PATTERN.fullmatch(ref) is None:
        raise InheritanceError("platform.ref must be immutable")

    extensions = data.get("extensions", {})
    for capability, mode in data["capabilities"].items():
        local = extensions.get(capability) if isinstance(extensions, Mapping) else None
        if mode in {"append", "override"} and not local:
            raise InheritanceError(f"{capability}: {mode} requires local content")
        if mode in {"inherit", "disable"} and local:
            raise InheritanceError(f"{capability}: {mode} cannot carry local content")

    ownership = data.get("ownership", {})
    entries: list[tuple[str, PurePosixPath]] = []
    if isinstance(ownership, Mapping):
        for owner, values in ownership.items():
            for value in values:
                entries.append((str(owner), _safe_path(str(value))))
    for index, (owner, path) in enumerate(entries):
        for other_owner, other_path in entries[index + 1 :]:
            if owner != other_owner and _paths_overlap(path, other_path):
                raise InheritanceError(
                    f"ambiguous ownership: {owner}:{path} overlaps {other_owner}:{other_path}"
                )


def resolve(data: Mapping[str, Any]) -> dict[str, ResolvedCapability]:
    """Resolve capabilities with stable provenance after validating the declaration."""
    validate_declaration(data)
    profile = data.get("profile")
    extensions = data.get("extensions", {})
    resolved: dict[str, ResolvedCapability] = {}
    for capability in CAPABILITIES:
        mode = str(data["capabilities"][capability])
        provenance = ["platform"]
        if profile is not None:
            provenance.append(f"profile:{profile}")
        local = tuple(extensions.get(capability, ())) if isinstance(extensions, Mapping) else ()
        if mode in {"append", "override"}:
            provenance.append("repository")
        resolved[capability] = ResolvedCapability(
            name=capability,
            mode=mode,
            enabled=mode != "disable",
            extensions=local,
            provenance=tuple(provenance),
        )
    return resolved


def doctor(root: Path) -> list[DoctorFinding]:
    """Return deterministic findings for an opted-in derived repository.

    Repositories without a declaration are not derived repositories and remain
    compatible with the pre-inheritance contract. A present declaration is
    validated and resolved fail closed; doctor never mutates repository state.
    """
    declaration_path = root / ".ai-native" / "derived.yaml"
    if not declaration_path.exists():
        return []
    try:
        data = load_declaration(declaration_path)
        resolved = resolve(data)
    except (OSError, yaml.YAMLError, InheritanceError) as exc:
        return [DoctorFinding("inheritance.invalid", str(exc), ".ai-native/derived.yaml")]

    missing = [name for name in CAPABILITIES if name not in resolved]
    if missing:
        return [
            DoctorFinding(
                "inheritance.resolution_incomplete",
                f"required capabilities did not resolve: {', '.join(missing)}",
                ".ai-native/derived.yaml",
            )
        ]
    return []
