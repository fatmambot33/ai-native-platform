"""Regression coverage for AI-review governance documentation boundaries."""

from pathlib import Path


def test_ai_review_governance_policy_is_codeowner_protected() -> None:
    """Security-sensitive AI-review policy must require code-owner review."""
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")

    assert "/docs/AI_REVIEW_GOVERNANCE.md @fatmambot33" in codeowners


def test_v030_release_notes_mark_ai_review_as_unreleased() -> None:
    """Do not advertise unreleased governance semantics as shipped in v0.3.0."""
    release_notes = Path("RELEASE_NOTES.md").read_text(encoding="utf-8")

    assert "## Unreleased AI-review governance preview" in release_notes
    assert "AI-review governance is not part of the v0.3.0 contract." in release_notes
