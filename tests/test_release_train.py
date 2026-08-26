"""Release-train tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ai_native import (
    CURRENT_MANIFEST_VERSION,
    Finding,
    migrate_manifest,
    sarif_payload,
    validate_manifest,
)
from tools.improvement_engine import discover, make_finding, sanitize
from tools.release_artifacts import build_metadata

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ("library", "cli", "service", "agent-tool", "plugin", "full-platform")


@pytest.mark.parametrize("profile", PROFILES)
def test_passing_profile_fixture(profile: str) -> None:
    """Every profile must have a fully passing repository fixture."""
    manifest = ROOT / "fixtures" / "passing" / f"{profile}.yaml"
    _, findings = validate_manifest(manifest, ROOT / "fixtures")
    assert findings == []


@pytest.mark.parametrize("profile", PROFILES)
def test_failing_profile_fixture(profile: str) -> None:
    """Every profile must have a focused failing repository fixture."""
    manifest = ROOT / "fixtures" / "failing" / f"{profile}.yaml"
    _, findings = validate_manifest(manifest, ROOT / "fixtures")
    codes = {finding.code for finding in findings}
    assert codes & {
        "schema.invalid",
        "profile.requirement_missing",
        "profile.agent_surface_missing",
        "profile.service_surface_missing",
    }


def test_plugin_fixture_exercises_credentials() -> None:
    """The plugin fixture covers local-only credentials and evidence."""
    path = ROOT / "fixtures" / "passing" / "plugin.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["plugin"]["credentials"]["required"] is True
    assert data["plugin"]["credentials"]["local_only"] is True
    assert data["evidence"]["paths"]["env_example"] == "evidence"
    assert data["evidence"]["paths"]["gitignore"] == "evidence"


def test_sarif_output_is_valid_shape() -> None:
    """SARIF output carries rules, locations, and manifest paths."""
    manifest = Path("fixture/AI_NATIVE_PLATFORM.yaml")
    payload = sarif_payload(
        manifest,
        [Finding("test.finding", "Example finding.", "product.profile")],
    )
    assert payload["version"] == "2.1.0"
    run = payload["runs"][0]
    assert run["tool"]["driver"]["rules"][0]["id"] == "test.finding"
    assert run["results"][0]["properties"]["manifestPath"] == "product.profile"


def test_upgrade_unversioned_manifest() -> None:
    """Legacy manifests upgrade deterministically to version one."""
    legacy = {
        "product": {
            "name": "legacy",
            "profile": "cli",
            "ai_native": True,
        },
        "interfaces": {"cli": True},
    }
    upgraded = migrate_manifest(legacy)
    assert upgraded["version"] == CURRENT_MANIFEST_VERSION
    assert upgraded["standard"]["ref"] == "v0.2.0"
    assert upgraded["product"]["name"] == "legacy"
    assert upgraded["interfaces"]["cli"] is True
    assert upgraded["interfaces"]["json_schema"] is True


def test_upgrade_existing_v0_1_manifest_renames_security_evidence() -> None:
    """The one-way upgrader rewrites the removed v0.1 security evidence key."""
    legacy = {
        "version": 1,
        "standard": {
            "repository": "fatmambot33/ai-native-platform",
            "ref": "v0.1.0",
        },
        "evidence": {
            "mode": "repository",
            "paths": {"security_workflow": ".github/workflows/security.yml"},
        },
    }

    upgraded = migrate_manifest(legacy)
    paths = upgraded["evidence"]["paths"]

    assert upgraded["standard"]["ref"] == "v0.2.0"
    assert paths["security_evidence"] == ".github/workflows/security.yml"
    assert "security_workflow" not in paths


def test_upgrade_rejects_future_manifest() -> None:
    """The CLI never silently downgrades an unknown future contract."""
    with pytest.raises(ValueError, match="newer than supported"):
        migrate_manifest({"version": 99})


def test_upgrade_cli_dry_run(tmp_path: Path) -> None:
    """Dry-run produces a diff and leaves the source untouched."""
    manifest = tmp_path / "AI_NATIVE_PLATFORM.yaml"
    manifest.write_text(
        "product:\n  name: legacy\n  profile: library\n  ai_native: true\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "ai_native.py"),
            "upgrade",
            str(manifest),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "+version: 1" in result.stdout
    assert not manifest.read_text(encoding="utf-8").startswith("version:")


def test_sanitize_redacts_secret_assignments() -> None:
    """Untrusted signals cannot leak common secret assignments."""
    text = sanitize("token=abc123 password: hunter2 safe text")
    assert "abc123" not in text
    assert "hunter2" not in text
    assert text.count("[REDACTED]") == 2


def test_fingerprint_is_stable() -> None:
    """Finding identity is deterministic."""
    first = make_finding("x", "Title", "Body", "path")
    second = make_finding("x", "Title", "Different body", "path")
    assert first.fingerprint == second.fingerprint


def test_discovery_budget_suppression_and_external_signals(tmp_path: Path) -> None:
    """Discovery deduplicates, suppresses, redacts, and enforces its issue budget."""
    for relative in (
        "pyproject.toml",
        "standard/AI_NATIVE_PLATFORM.yaml",
        "templates/AI_NATIVE_PLATFORM.yaml",
        "CHANGELOG.md",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text((ROOT / relative).read_text(encoding="utf-8"))

    for state in ("passing", "failing"):
        shutil.copytree(ROOT / "fixtures" / state, tmp_path / "fixtures" / state)
    shutil.copytree(ROOT / "fixtures" / "evidence", tmp_path / "fixtures" / "evidence")

    signals = tmp_path / ".ai-native" / "signals.json"
    signals.parent.mkdir(parents=True)
    signals.write_text(
        json.dumps(
            [
                {
                    "kind": "ci",
                    "code": "ci.failure",
                    "title": "CI failed token=super-secret",
                    "body": "password: hidden",
                    "path": ".github/workflows/quality.yml",
                    "severity": "high",
                },
                {
                    "kind": "ci",
                    "code": "ci.failure",
                    "title": "CI failed token=super-secret",
                    "body": "duplicate",
                    "path": ".github/workflows/quality.yml",
                    "severity": "high",
                },
                {
                    "kind": "documentation",
                    "code": "docs.stale",
                    "title": "Docs stale",
                    "body": "Update docs",
                    "status": "deferred",
                },
            ]
        ),
        encoding="utf-8",
    )
    findings = discover(tmp_path, budget=1, include_canonical=False)
    assert len(findings) == 1
    assert findings[0].code == "ci.failure"
    assert "super-secret" not in findings[0].title
    assert "hidden" not in findings[0].body

    suppression = tmp_path / ".ai-native" / "suppressions.yaml"
    suppression.write_text(
        yaml.safe_dump({"suppressions": [{"code": "ci.failure"}]}),
        encoding="utf-8",
    )
    assert discover(tmp_path, budget=5, include_canonical=False) == []


def test_release_metadata(tmp_path: Path) -> None:
    """Release metadata includes checksums, SPDX, and current-version provenance."""
    (tmp_path / "pyproject.toml").write_text(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "ai_native_platform-0.2.0-py3-none-any.whl"
    artifact.write_bytes(b"wheel")
    outputs = build_metadata(tmp_path, dist)
    assert outputs["checksums"].is_file()
    sbom = json.loads(outputs["sbom"].read_text(encoding="utf-8"))
    provenance = json.loads(outputs["provenance"].read_text(encoding="utf-8"))
    assert sbom["spdxVersion"] == "SPDX-2.3"
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    build_type = provenance["predicate"]["buildDefinition"]["buildType"]
    assert build_type.endswith("/blob/v0.2.0/.github/workflows/release.yml")
