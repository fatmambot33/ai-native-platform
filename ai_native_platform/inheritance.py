"""Validate and resolve AI Native derived-repository declarations."""

from __future__ import annotations

import json
import re
import sysconfig
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

CAPABILITIES = ("welcome", "troubleshooting", "update", "doctor")
PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "library": {capability: () for capability in CAPABILITIES}
}
REF_PATTERN = re.compile(r"(?:[0-9a-f]{40}|v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
SCHEMA_NAME = "ai-native-derived.schema.json"


class InheritanceError(ValueError):
    """Raised when a derived-repository declaration is unsafe or inconsistent."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    """Construct one mapping while rejecting ambiguous duplicate keys."""
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise InheritanceError("derived declaration contains an invalid mapping key") from exc
        if duplicate:
            raise InheritanceError(f"duplicate declaration key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


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
    """Return the inheritance schema from a checkout or installed distribution."""
    checkout = Path(__file__).resolve().parents[1] / "schemas" / SCHEMA_NAME
    if checkout.is_file():
        return checkout
    installed = Path(sysconfig.get_path("data")) / "share" / "ai-native-platform" / SCHEMA_NAME
    if installed.is_file():
        return installed
    raise FileNotFoundError(f"Unable to locate {SCHEMA_NAME}")


def load_declaration(path: Path) -> dict[str, Any]:
    """Load a derived-repository YAML declaration without ambiguous keys."""
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise InheritanceError("derived declaration must contain a mapping")
    return data


def _schema_errors(data: Mapping[str, Any]) -> list[str]:
    """Return stable JSON Schema validation errors."""
    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def _safe_path(value: str) -> PurePosixPath:
    """Validate and normalize one portable repository-relative ownership path."""
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        not value
        or "\0" in value
        or "\\" in value
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
        or "." in posix_path.parts
    ):
        raise InheritanceError(f"unsafe ownership path: {value!r}")
    return posix_path


def _portable_path(path: PurePosixPath) -> PurePosixPath:
    """Normalize a path for portable case-insensitive ownership comparison."""
    return PurePosixPath(*(part.casefold() for part in path.parts))


def _paths_overlap(left: PurePosixPath, right: PurePosixPath) -> bool:
    """Return whether two ownership paths overlap hierarchically on supported filesystems."""
    left = _portable_path(left)
    right = _portable_path(right)
    return left == right or left in right.parents or right in left.parents


def validate_declaration(data: Mapping[str, Any]) -> None:
    """Validate schema plus cross-field inheritance invariants."""
    errors = _schema_errors(data)
    if errors:
        raise InheritanceError("; ".join(errors))

    ref = str(data["platform"]["ref"])
    if REF_PATTERN.fullmatch(ref) is None:
        raise InheritanceError("platform.ref must be immutable")

    profile = data.get("profile")
    if profile is not None and profile not in PROFILES:
        raise InheritanceError(f"unknown profile: {profile!r}")

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
    try:
        declaration_path.lstat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        return [DoctorFinding("inheritance.invalid", str(exc), ".ai-native/derived.yaml")]

    try:
        data = load_declaration(declaration_path)
        resolved = resolve(data)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        SchemaError,
        yaml.YAMLError,
        InheritanceError,
    ) as exc:
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
