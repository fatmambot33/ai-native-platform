"""Focused regressions for the final PR #35 governance remediation batch."""

from pathlib import Path

import ai_native

ROOT = Path(__file__).resolve().parents[1]


def test_dependabot_configuration_is_codeowner_protected() -> None:
    """Keep credential-bearing Dependabot configuration under code-owner review."""
    codeowners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert "/.github/dependabot.yml @fatmambot33" in codeowners


def test_revision_run_cache_is_published_atomically() -> None:
    """Never publish partial paginated workflow-run data as trusted cache state."""
    preflight = (
        ROOT / "actions" / "codex-review-gate" / "preflight.sh"
    ).read_text(encoding="utf-8")
    assert 'tmp_cache="${REVISION_RUNS_CACHE_FILE}.tmp.$$"' in preflight
    assert 'jq -s \'.\' >"$tmp_cache"' in preflight
    assert 'mv "$tmp_cache" "$REVISION_RUNS_CACHE_FILE"' in preflight
    assert preflight.count('rm -f "$tmp_cache"') >= 2



def test_workflow_namespace_owner_rule_rejects_later_ownerless_override(tmp_path: Path) -> None:
    """Reject a predictable-probe bypass after an ownerless workflow override."""
    github = tmp_path / ".github"
    github.mkdir(exist_ok=True)
    codeowners = github / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @fatmambot33\n"
        "/.github/workflows/**\n"
        "/.github/workflows/__ai_native_unmatched_probe__.yml @fatmambot33\n",
        encoding="utf-8",
    )
    assert not ai_native._codeowners_has_workflow_namespace_rule(tmp_path)

    codeowners.write_text(
        "/.github/workflows/** @fatmambot33\n"
        "/.github/CODEOWNERS @fatmambot33\n",
        encoding="utf-8",
    )
    assert ai_native._codeowners_has_workflow_namespace_rule(tmp_path)


def test_dependabot_configuration_is_canonically_governed() -> None:
    """Keep Dependabot in the canonical governed-path self-check."""
    validator_text = (ROOT / "validator" / "validate_standard.py").read_text(
        encoding="utf-8"
    )
    assert '".github/dependabot.yml"' in validator_text
