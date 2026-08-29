"""Regression tests for the Codex review gate trust boundary."""

from __future__ import annotations

from pathlib import Path


GATE = Path("actions/codex-review-gate/codex-review-gate.sh")


def _function_body(script: str, name: str) -> str:
    """Return one simple shell function body from the gate script."""
    start = script.index(f"{name}() {{")
    remainder = script[start:]
    return remainder.split("\n}\n", 1)[0]


def test_bootstrap_clean_reaction_requires_trusted_unedited_head_marker() -> None:
    script = GATE.read_text(encoding="utf-8")
    bootstrap = _function_body(script, "find_bootstrap_trigger_comment")

    assert '(.author_association // "") == "OWNER"' in bootstrap
    assert '(.author_association // "") == "MEMBER"' in bootstrap
    assert '(.author_association // "") == "COLLABORATOR"' in bootstrap
    assert '(.created_at // "") == (.updated_at // "")' in bootstrap
    assert 'test("^@codex review' in bootstrap
    assert "contains($marker)" in bootstrap


def test_request_mode_never_uses_maintainer_bootstrap_fallback() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    trigger = _function_body(script, "find_trigger_comment")

    assert "find_bot_trigger_comment" in request
    assert "find_bootstrap_trigger_comment" not in request
    assert "find_bot_trigger_comment" in trigger
    assert 'if [[ -z "$COMMENT_ID" ]]' in trigger
    assert "find_bootstrap_trigger_comment" in trigger
