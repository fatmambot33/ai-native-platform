"""Regression tests for the Codex review gate trust boundary."""

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


def test_clean_reaction_request_must_postdate_current_head_activation() -> None:
    script = GATE.read_text(encoding="utf-8")
    bot = _function_body(script, "find_bot_trigger_comment")
    bootstrap = _function_body(script, "find_bootstrap_trigger_comment")

    assert ".pull_request.updated_at" in script
    assert 'select((.pull_request.head.sha // "") == $head)' in script
    for body in (bot, bootstrap):
        assert '--arg active_since "$HEAD_ACTIVE_SINCE"' in body
        assert 'select((.created_at // "") >= $active_since)' in body


def test_thread_pagination_errors_fail_closed() -> None:
    script = GATE.read_text(encoding="utf-8")
    threads = _function_body(script, "has_unresolved_codex_threads")
    clear = _function_body(script, "has_clear_codex_evidence")

    assert 'if ! response="$(gh api "${args[@]}")"' in threads
    assert "return 2" in threads
    assert "(.errors? // [])" in threads
    assert "malformed or errored Codex review-thread data" in threads
    assert "thread_status" in clear
    assert 'if [[ "$thread_status" -eq 1 ]]' in clear
    assert "Unable to prove that all Codex review threads are resolved" in clear
