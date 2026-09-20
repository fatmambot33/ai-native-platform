"""Tests for the installed AI Native CLI entry point."""

import argparse

import pytest
import yaml

import ai_native_entry

PLATFORM_REF = "b2793f9fae645df1bda7492da01627396fc5e29f"


def _declaration() -> dict:
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": PLATFORM_REF,
        },
        "profile": "library",
        "capabilities": {
            "welcome": "inherit",
            "troubleshooting": "inherit",
            "update": "inherit",
            "doctor": "inherit",
        },
    }


def test_public_doctor_rejects_invalid_inheritance(tmp_path, monkeypatch, capsys) -> None:
    declaration = _declaration()
    declaration["platform"]["ref"] = "main"
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", lambda args: 0)
    args = argparse.Namespace(root=str(tmp_path), manifest=str(tmp_path / "manifest.yaml"))
    assert ai_native_entry.command_doctor(args) == 1
    assert "FAIL Repository inheritance: inheritance.invalid" in capsys.readouterr().out


def test_public_doctor_accepts_valid_inheritance(tmp_path, monkeypatch, capsys) -> None:
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(_declaration()), encoding="utf-8")
    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", lambda args: 0)
    args = argparse.Namespace(root=str(tmp_path), manifest=str(tmp_path / "manifest.yaml"))
    assert ai_native_entry.command_doctor(args) == 0
    assert "PASS Repository inheritance" in capsys.readouterr().out


def test_public_doctor_handles_root_resolution_failure_before_base_doctor(
    tmp_path, monkeypatch, capsys
) -> None:
    """A symlink-loop root must fail deterministically before base validation."""
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(loop)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")

    called = False

    def base_doctor(args):
        nonlocal called
        called = True
        raise AssertionError("base doctor must not run for an unresolvable root")

    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", base_doctor)
    args = argparse.Namespace(root=str(loop), manifest=str(tmp_path / "manifest.yaml"))
    assert ai_native_entry.command_doctor(args) == 1
    assert called is False
    assert "cannot resolve repository root" in capsys.readouterr().out
