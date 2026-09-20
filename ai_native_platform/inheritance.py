"""Validate and resolve AI Native derived-repository declarations."""

from __future__ import annotations

import json
import re
import stat
import sysconfig
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing.exceptions import Unresolvable

CAPABILITIES = ("welcome", "troubleshooting", "update", "doctor")
PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "library": {capability: () for capability in CAPABILITIES}
}
_SEMVER_CORE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
_SEMVER_IDENTIFIER = r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
_SEMVER_PRERELEASE = rf"(?:-{_SEMVER_IDENTIFIER}(?:\.{_SEMVER_IDENTIFIER})*)?"
_SEMVER_BUILD = r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
_SEMVER = rf"{_SEMVER_CORE}{_SEMVER_PRERELEASE}{_SEMVER_BUILD}"
REF_PATTERN = re.compile(rf"(?:[0-9a-f]{{40}}|v?{_SEMVER})")
SCHEMA_NAME = "ai-native-derived.schema.json"
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CONIN$",
    "CONOUT$",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    *(f"COM{i}" for i in "¹²³"),
    *(f"LPT{i}" for i in "¹²³"),
}
_WINDOWS_INVALID = frozenset('<>:"|?*')
_MAX_PORTABLE_COMPONENT_BYTES = 255
_MAX_PORTABLE_PATH_BYTES = 260


class InheritanceError(ValueError):
    """Raised when a derived-repository declaration is unsafe or inconsistent."""


class _LoadedDeclaration(dict[str, Any]):
    """Declaration mapping retaining its source path for canonical validation."""

    source_path: Path


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
    loaded = _LoadedDeclaration(data)
    loaded.source_path = path
    return loaded


def _iter_schema_references(value: object):
    """Yield every JSON Schema reference in deterministic document order."""
    if isinstance(value, dict):
        reference = value.get("$ref")
        if reference is not None:
            if not isinstance(reference, str):
                raise InheritanceError("schema $ref values must be strings")
            yield reference
        for child in value.values():
            yield from _iter_schema_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_schema_references(child)


def _validate_schema_references(schema: Mapping[str, Any]) -> None:
    """Resolve schema references with the same resolver used at runtime."""
    validator = Draft202012Validator(schema)
    for reference in _iter_schema_references(schema):
        if not reference.startswith("#"):
            raise InheritanceError(f"schema reference must be local: {reference!r}")
        validator._resolver.lookup(reference)  # noqa: SLF001


def _validate_schema_contract(schema: Mapping[str, Any]) -> None:
    """Ensure the canonical derived schema still rejects key invalid declarations."""
    validator = Draft202012Validator(schema)
    invalid_declarations = (
        {},
        {"version": 1, "platform": {}, "capabilities": {}},
        {
            "version": 2,
            "platform": {"repository": "fatmambot33/ai-native-platform", "ref": "v1.0.0"},
            "capabilities": {name: "inherit" for name in CAPABILITIES},
        },
        {
            "version": 1,
            "platform": {"repository": "fatmambot33/ai-native-platform", "ref": "v1.0.0"},
            "capabilities": {**{name: "inherit" for name in CAPABILITIES}, "extra": "inherit"},
        },
        {
            "version": 1,
            "platform": {"repository": "fatmambot33/ai-native-platform", "ref": "v1.0.0"},
            "capabilities": {**{name: "inherit" for name in CAPABILITIES}, "welcome": "magic"},
        },
        {
            "version": 1,
            "platform": {"repository": "fatmambot33/ai-native-platform", "ref": "v1.0.0"},
            "capabilities": {name: "inherit" for name in CAPABILITIES},
            "unexpected": True,
        },
    )
    for candidate in invalid_declarations:
        if not list(validator.iter_errors(candidate)):
            raise InheritanceError("derived schema does not enforce the v1 fail-closed contract")


def _canonical_schema_for(data: Mapping[str, Any]) -> Path | None:
    """Return an available checkout-local schema for a loaded canonical starter."""
    if not isinstance(data, _LoadedDeclaration):
        return None
    source = data.source_path
    if source.name != "derived.yaml" or source.parent.name != "templates":
        return None
    candidate = source.parent.parent / "schemas" / SCHEMA_NAME
    return candidate if candidate.is_file() else None


def _schema_errors(data: Mapping[str, Any], schema_path: Path | None = None) -> list[str]:
    """Return stable JSON Schema validation errors."""
    path = _schema_path() if schema_path is None else schema_path
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    _validate_schema_references(schema)
    if path.name == SCHEMA_NAME:
        _validate_schema_contract(schema)
    validator = Draft202012Validator(schema)
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def _safe_path(value: str) -> PurePosixPath:
    """Validate and normalize one portable repository-relative ownership path."""
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    unsafe_component = any(
        not part
        or len(part.encode("utf-8")) > _MAX_PORTABLE_COMPONENT_BYTES
        or part.endswith((" ", "."))
        or any(char in _WINDOWS_INVALID or ord(char) < 32 for char in part)
        or part.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_RESERVED
        for part in posix_path.parts
    )
    if (
        not value
        or len(value.encode("utf-8")) > _MAX_PORTABLE_PATH_BYTES
        or "\0" in value
        or "\\" in value
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
        or "." in posix_path.parts
        or unsafe_component
    ):
        raise InheritanceError(f"unsafe ownership path: {value!r}")
    return posix_path


def _portable_parts(path: PurePosixPath) -> tuple[str, ...]:
    """Return canonical path components for portable ownership comparison."""
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


def _validate_ownership(entries: list[tuple[str, PurePosixPath]]) -> None:
    """Reject cross-owner aliases and prefixes in near-linear time."""
    root: dict[str, Any] = {"owners": set(), "children": {}}
    for owner, path in entries:
        node = root
        parts = _portable_parts(path)
        for part in parts:
            other = node["owners"] - {owner}
            if other:
                raise InheritanceError(
                    f"ambiguous ownership: {owner}:{path} overlaps owner {sorted(other)[0]}"
                )
            node = node["children"].setdefault(part, {"owners": set(), "children": {}})
        stack = [node]
        while stack:
            descendant = stack.pop()
            other = descendant["owners"] - {owner}
            if other:
                raise InheritanceError(
                    f"ambiguous ownership: {owner}:{path} overlaps owner {sorted(other)[0]}"
                )
            stack.extend(descendant["children"].values())
        node["owners"].add(owner)


def validate_declaration(
    data: Mapping[str, Any], *, schema_path: Path | None = None
) -> None:
    """Validate schema plus cross-field inheritance invariants.

    Parameters
    ----------
    data:
        Parsed derived-repository declaration.
    schema_path:
        Optional schema to validate against. Canonical repository validation
        supplies the schema from the checkout being inspected; runtime callers
        use the packaged schema when this is omitted.
    """
    effective_schema = schema_path or _canonical_schema_for(data)
    errors = _schema_errors(data, effective_schema)
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
    _validate_ownership(entries)


def resolve(data: Mapping[str, Any]) -> dict[str, ResolvedCapability]:
    """Resolve capabilities with stable provenance after validating the declaration."""
    validate_declaration(data)
    profile = data.get("profile")
    extensions = data.get("extensions", {})
    resolved: dict[str, ResolvedCapability] = {}
    for capability in CAPABILITIES:
        mode = str(data["capabilities"][capability])
        inherited = ["platform"]
        if profile is not None:
            inherited.append(f"profile:{profile}")
        local = tuple(extensions.get(capability, ())) if isinstance(extensions, Mapping) else ()
        if mode == "inherit":
            provenance = inherited
        elif mode == "append":
            provenance = [*inherited, "repository"]
        else:
            provenance = ["repository"]
        resolved[capability] = ResolvedCapability(
            name=capability,
            mode=mode,
            enabled=mode != "disable",
            extensions=local,
            provenance=tuple(provenance),
        )
    return resolved


def _require_regular_declaration(root: Path, declaration_path: Path) -> bool:
    """Check for a repository-owned declaration without following symlinks."""
    ai_native = root / ".ai-native"
    directory_stat = ai_native.lstat()
    if stat.S_ISLNK(directory_stat.st_mode):
        raise InheritanceError(".ai-native must not be a symlink")
    if not stat.S_ISDIR(directory_stat.st_mode):
        return False
    declaration_stat = declaration_path.lstat()
    if stat.S_ISLNK(declaration_stat.st_mode) or not stat.S_ISREG(declaration_stat.st_mode):
        raise InheritanceError("derived declaration must be a regular file")
    return True


def doctor(root: Path) -> list[DoctorFinding]:
    """Return deterministic findings for an opted-in derived repository.

    Repositories without a declaration are not derived repositories and remain
    compatible with the pre-inheritance contract. A present declaration is
    validated and resolved fail closed; doctor never mutates repository state.
    """
    declaration_path = root / ".ai-native" / "derived.yaml"
    try:
        if not _require_regular_declaration(root, declaration_path):
            return []
    except FileNotFoundError:
        return []
    except (OSError, InheritanceError) as exc:
        return [DoctorFinding("inheritance.invalid", str(exc), ".ai-native/derived.yaml")]

    try:
        data = load_declaration(declaration_path)
        resolved = resolve(data)
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