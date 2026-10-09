"""Tests for the installed AI Native CLI entry point."""

import argparse

import pytest
import yaml

import ai_native_entry

PLATFORM_REF = "3e49406e8ac3a9c1f28c6f91b9356ff24a5f41cc"


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


def test_ai_native_main_routes_doctor_through_inheritance(tmp_path, monkeypatch, capsys) -> None:
    """The module/script entry path must not bypass inheritance validation."""
    import ai_native

    declaration = _declaration()
    declaration["platform"]["ref"] = "main"
    path = tmp_path / ".ai-native" / "derived.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(declaration), encoding="utf-8")
    monkeypatch.setattr(ai_native, "command_doctor", lambda args: 0)

    assert ai_native.main(["doctor", "--root", str(tmp_path)]) == 1
    assert "FAIL Repository inheritance" in capsys.readouterr().out


def test_doctor_default_manifest_is_relative_to_root(tmp_path, monkeypatch) -> None:
    """Selecting a repository root must not read a manifest from the caller CWD."""
    repository = tmp_path / "repository"
    repository.mkdir()
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    observed = []

    def base_doctor(args):
        observed.append((args.root, args.manifest))
        return 0

    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", base_doctor)
    assert ai_native_entry.main(["doctor", "--root", str(repository)]) == 0
    assert observed == [(str(repository), str(repository / "AI_NATIVE_PLATFORM.yaml"))]


def test_doctor_explicit_manifest_remains_caller_relative(tmp_path, monkeypatch) -> None:
    """An explicitly selected manifest keeps the established CLI path semantics."""
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.chdir(tmp_path)
    observed = []

    def base_doctor(args):
        observed.append(args.manifest)
        return 0

    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", base_doctor)
    assert ai_native_entry.main(["doctor", "custom.yaml", "--root", str(repository)]) == 0
    assert observed == ["custom.yaml"]


def test_doctor_explicit_default_named_manifest_stays_caller_relative(
    tmp_path, monkeypatch
) -> None:
    """An explicit default-named file must not be rewritten under --root."""
    repository = tmp_path / "repository"
    repository.mkdir()
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)
    observed = []

    def base_doctor(args):
        observed.append((args.root, args.manifest))
        return 0

    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", base_doctor)
    assert ai_native_entry.main(
        ["doctor", "AI_NATIVE_PLATFORM.yaml", "--root", str(repository)]
    ) == 0
    assert observed == [(str(repository), "AI_NATIVE_PLATFORM.yaml")]


def test_doctor_without_manifest_or_root_uses_current_repository(
    tmp_path, monkeypatch
) -> None:
    """Omitting both CLI arguments resolves the default under the caller root."""
    monkeypatch.chdir(tmp_path)
    observed = []

    def base_doctor(args):
        observed.append((args.root, args.manifest))
        return 0

    monkeypatch.setattr(ai_native_entry.ai_native, "command_doctor", base_doctor)
    assert ai_native_entry.main(["doctor"]) == 0
    assert observed == [(str(tmp_path), str(tmp_path / "AI_NATIVE_PLATFORM.yaml"))]


@pytest.mark.parametrize("explicit", (False, True))
def test_doctor_checks_actual_manifest_location(tmp_path, monkeypatch, explicit) -> None:
    """The base doctor must inspect the intended manifest when roots differ."""
    repository = tmp_path / "repository"
    repository.mkdir()
    caller = tmp_path / "caller"
    caller.mkdir()
    for directory in (repository, caller):
        (directory / "AI_NATIVE_PLATFORM.yaml").write_text("version: 2\n", encoding="utf-8")
    monkeypatch.chdir(caller)
    observed = []

    def validate_manifest(manifest, root):
        observed.append((manifest.resolve(), root.resolve()))
        return {}, []

    monkeypatch.setattr(ai_native_entry.ai_native, "validate_manifest", validate_manifest)
    argv = ["doctor", "--root", str(repository)]
    if explicit:
        argv.append("AI_NATIVE_PLATFORM.yaml")

    assert ai_native_entry.main(argv) == 0
    chosen = caller if explicit else repository
    assert observed == [(chosen / "AI_NATIVE_PLATFORM.yaml", repository)]
