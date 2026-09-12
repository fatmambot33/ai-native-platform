"""Regression tests for the Codex review gate trust boundary."""

from pathlib import Path

GATE = Path("actions/codex-review-gate/codex-review-gate.sh")


def _function_body(script: str, name: str) -> str:
    """Return one simple shell function body from the gate script."""
    start = script.index(f"{name}() {{")
    remainder = script[start:]
    return remainder.split("\n}\n", 1)[0]


def test_bootstrap_reaction_is_not_accepted_as_clean_evidence() -> None:
    script = GATE.read_text(encoding="utf-8")
    bootstrap = _function_body(script, "find_bootstrap_trigger_comment")
    reaction = _function_body(script, "has_trigger_clean_reaction")
    review = _function_body(script, "has_matching_review")

    assert '(.author_association // "") == "OWNER"' in bootstrap
    assert "find_bot_trigger_comment" in reaction
    assert "find_trigger_comment" not in reaction
    assert "find_trigger_comment" in review
    assert "commit_id" in review
    assert "$head" in review
    assert ".submitted_at" in review


def test_request_mode_never_uses_maintainer_bootstrap_fallback() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    trigger = _function_body(script, "find_trigger_comment")

    assert "find_bot_trigger_comment" in request
    assert "find_bootstrap_trigger_comment" not in request
    assert "find_bot_trigger_comment" in trigger
    assert 'if [[ -z "$COMMENT_ID" ]]' in trigger
    assert "find_bootstrap_trigger_comment" in trigger


def test_clean_reaction_request_uses_trusted_run_provenance() -> None:
    script = GATE.read_text(encoding="utf-8")
    trusted = _function_body(script, "trusted_request_run")
    bot = _function_body(script, "find_bot_trigger_comment")

    assert ".pull_request.updated_at" not in script
    assert '.event == "pull_request_target"' in trusted
    assert ".workflow_id" in trusted
    assert ".path == $workflow_path" in trusted
    assert ".pull_requests[]?" in trusted
    assert '(.head.sha // "") == $head' in trusted
    assert '(.base.sha // "") == $base' in trusted
    assert "ai-native-codex-review-run" in bot


def test_request_comment_records_request_run_id() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert "RUN_MARKER" in script
    assert '"$RUN_MARKER"' in request


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


def test_matching_review_must_follow_current_head_base_request() -> None:
    script = GATE.read_text(encoding="utf-8")
    review = _function_body(script, "has_matching_review")

    assert "find_trigger_comment" in review
    assert "COMMENT_CREATED_AT" in review
    assert ".submitted_at" in review
    assert "$since" in review
    assert "${HEAD_SHA}:${BASE_SHA}" in script


def test_explicit_label_can_replace_a_dismissed_review() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    dismissed = _function_body(script, "has_dismissed_matching_review")

    assert "DISMISSED" in dismissed
    assert "has_dismissed_matching_review" in request
    assert "authorizes one replacement review" in request


def test_review_requests_are_quota_aware() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    failure = _function_body(script, "codex_failure_after")

    assert 'REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"' in script
    assert "still pending; preserving quota" in request
    assert "reached your Codex usage limits for code reviews" in failure
    assert "No automatic retry will be attempted" in failure


def test_ready_for_review_reuses_native_codex_evidence() -> None:
    script = GATE.read_text(encoding="utf-8")
    native_event = _function_body(script, "is_native_review_event")
    native_review = _function_body(script, "has_native_matching_review")
    native_reaction = _function_body(script, "has_native_clean_reaction")

    assert "ready_for_review" in native_event
    assert "opened" in native_event
    assert "commit_id" in native_review
    assert "$head" in native_review
    assert "submitted_at" in native_review
    assert "$since" in native_review
    assert "issues/${PR_NUMBER}/reactions?per_page=100" in native_reaction
    assert "+1" in native_reaction
    assert "created_at" in native_reaction
    assert "$since" in native_reaction
    assert "no duplicate request will be sent" in script
