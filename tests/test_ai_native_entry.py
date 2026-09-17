"""Tests for the installed AI Native CLI entry point."""

import argparse

import yaml

import ai_native_entry


def _declaration() -> dict:
    return {
        "version": 1,
        "platform": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": "v0.3.0",
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
    """The installed doctor command fails when an opted-in declaration is invalid."""
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
    """The installed doctor command preserves success for a valid declaration."""
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(_declaration()), encoding="utf-8")
    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", lambda args: 0)
    args = argparse.Namespace(root=str(tmp_path), manifest=str(tmp_path / "manifest.yaml"))

    assert ai_native_entry.command_doctor(args) == 0
    assert "PASS Repository inheritance" in capsys.readouterr().out
