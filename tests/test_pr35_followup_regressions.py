"""Focused regressions for the final PR #35 governance remediation batch."""

from pathlib import Path

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
