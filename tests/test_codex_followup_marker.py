"""Tiny guard for the Codex follow-up documentation."""

from pathlib import Path


def test_codex_followup_references_tracking_issue() -> None:
    """The follow-up note should remain tied to the tracking issue."""
    text = Path("docs/CODEX_FOLLOWUP.md").read_text(encoding="utf-8")

    assert "Issue #33" in text
