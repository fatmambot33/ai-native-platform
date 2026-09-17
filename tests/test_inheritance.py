"""Tests for the AI Native inheritance contract."""

import copy

import pytest

from tools.inheritance import InheritanceError, resolve, validate_declaration


def declaration() -> dict:
    """Return a minimal valid derived-repository declaration."""
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": "v0.3.0",
        },
        "profile": "python-library",
        "capabilities": {
            "welcome": "inherit",
            "troubleshooting": "inherit",
            "update": "inherit",
            "doctor": "inherit",
        },
        "ownership": {"local": ["src/local.py"]},
    }


def test_resolve_is_deterministic_and_records_provenance() -> None:
    """Identical declarations resolve to identical explicit provenance."""
    candidate = declaration()
    assert resolve(candidate) == resolve(copy.deepcopy(candidate))
    welcome = resolve(candidate)["welcome"]
    assert welcome.enabled is True
    assert welcome.provenance == ("platform", "profile:python-library")


def test_append_requires_and_records_local_content() -> None:
    """Append is explicit and cannot silently omit repository content."""
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "append"
    with pytest.raises(InheritanceError, match="requires local content"):
        validate_declaration(candidate)
    candidate["extensions"] = {"welcome": ["docs/welcome-local.md"]}
    resolved = resolve(candidate)["welcome"]
    assert resolved.extensions == ("docs/welcome-local.md",)
    assert resolved.provenance[-1] == "repository"


def test_inherit_and_disable_reject_extensions() -> None:
    """Modes without local composition reject contradictory extension data."""
    for mode in ("inherit", "disable"):
        candidate = declaration()
        candidate["capabilities"]["doctor"] = mode
        candidate["extensions"] = {"doctor": ["doctor-local"]}
        with pytest.raises(InheritanceError, match="cannot carry local content"):
            validate_declaration(candidate)


def test_unknown_contract_profile_capability_and_mode_fail_closed() -> None:
    """Unsupported contract vocabulary never falls through as local behavior."""
    mutations = [
        ("version", 2),
        ("profile", "unknown"),
    ]
    for key, value in mutations:
        candidate = declaration()
        candidate[key] = value
        with pytest.raises(InheritanceError):
            validate_declaration(candidate)

    candidate = declaration()
    candidate["capabilities"]["extra"] = "inherit"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
    candidate = declaration()
    candidate["capabilities"]["welcome"] = "magic"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)


def test_ownership_rejects_escape_and_cross_owner_overlap() -> None:
    """Ownership is repository-relative and cannot be ambiguous across owners."""
    candidate = declaration()
    candidate["ownership"] = {"local": ["../outside"]}
    with pytest.raises(InheritanceError, match="unsafe ownership path"):
        validate_declaration(candidate)

    candidate = declaration()
    candidate["ownership"] = {
        "managed": ["docs"],
        "local": ["docs/local.md"],
    }
    with pytest.raises(InheritanceError, match="ambiguous ownership"):
        validate_declaration(candidate)


def test_platform_reference_and_repository_are_fail_closed() -> None:
    """Derived repositories must pin the canonical platform immutably."""
    candidate = declaration()
    candidate["platform"]["ref"] = "main"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
    candidate = declaration()
    candidate["platform"]["repository"] = "example/other"
    with pytest.raises(InheritanceError):
        validate_declaration(candidate)
