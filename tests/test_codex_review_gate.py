"""Regression tests for the canonical current-HEAD Codex review gate."""

from __future__ import annotations

from pathlib import Path

GATE = Path("actions/codex-review-gate/codex-review-gate.sh")


def _function_body(script: str, name: str) -> str:
    """Return one shell function body from the gate source."""
    start = script.index(f"{name}() {{")
    remainder = script[start:]
    end = remainder.index("\n}\n")
    return remainder[: end + 3]


def test_gate_requires_current_head_and_base_marker() -> None:
    script = GATE.read_text(encoding="utf-8")

    assert "HEAD_SHA" in script
    assert "BASE_SHA" in script
    assert "ai-native-codex-review-gate" in script
    assert "MARKER" in script


def test_gate_requires_server_verifiable_request_provenance() -> None:
    script = GATE.read_text(encoding="utf-8")
    trusted = _function_body(script, "trusted_request_run")
    bot = _function_body(script, "find_bot_trigger_comment")

    assert "GITHUB_RUN_ID" in script
    assert "GITHUB_WORKFLOW_REF" in script
    assert "current_workflow_id" in trusted
    assert '"pull_request_target"' in trusted
    assert ".workflow_id" in trusted
    assert ".path" in trusted
    assert ".head.sha" in trusted
    assert ".base.sha" in trusted
    assert "created_at" in trusted
    assert "github-actions[bot]" in bot
    assert "ai-native-codex-review-run" in bot
    assert "trusted_request_run" in bot


def test_bootstrap_reactions_are_not_trusted() -> None:
    script = GATE.read_text(encoding="utf-8")
    reaction = _function_body(script, "has_trigger_clean_reaction")

    assert "find_bot_trigger_comment" in reaction
    assert "find_trigger_comment" not in reaction


def test_gate_requires_current_head_review_submission() -> None:
    script = GATE.read_text(encoding="utf-8")
    review = _function_body(script, "has_matching_review")

    assert ".commit_id" in review
    assert "$head" in review
    assert ".submitted_at" in review


def test_gate_rejects_unresolved_codex_threads_fail_closed() -> None:
    script = GATE.read_text(encoding="utf-8")
    threads = _function_body(script, "has_unresolved_codex_threads")
    clear = _function_body(script, "has_clear_codex_evidence")

    assert "reviewThreads(first: 100, after: $cursor)" in threads
    assert "pageInfo { hasNextPage endCursor }" in threads
    assert "hasNextPage" in threads
    assert "endCursor" in threads
    assert "Unable to query Codex review-thread state" in threads
    assert "malformed or errored Codex review-thread data" in threads
    assert "has_unresolved_codex_threads" in clear
    assert 'if [[ "$thread_status" -eq 1 ]]' in clear
    assert "Unable to prove that all Codex review threads are resolved" in clear


def test_matching_review_must_follow_current_head_base_request() -> None:
    script = GATE.read_text(encoding="utf-8")
    review = _function_body(script, "has_matching_review")

    assert "find_trigger_comment" in review
    assert "COMMENT_CREATED_AT" in review
    assert ".submitted_at" in review
    assert "$since" in review
    assert 'REVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-${BASE_SHA}}"' in script
    assert "${HEAD_SHA}:${REVIEW_CONTEXT}" in script


def test_explicit_label_can_replace_a_dismissed_review() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")
    dismissed = _function_body(script, "has_dismissed_matching_review")

    assert "DISMISSED" in dismissed
    assert "has_dismissed_matching_review" in request
    assert "is_request_label_event" in request


def test_gate_does_not_auto_retry_review_requests() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert "is_request_label_event" in request
    assert "already exists" in request
    assert "No automatic retry will be attempted" in script


def test_gate_validates_request_comments_without_mutating_them() -> None:
    script = GATE.read_text(encoding="utf-8")

    assert "issues/comments/${COMMENT_ID}" not in script
    assert "--method PATCH" not in script


def test_request_mode_only_runs_on_explicit_label_event() -> None:
    script = GATE.read_text(encoding="utf-8")
    labeled = _function_body(script, "is_request_label_event")

    assert "pull_request_target" in labeled
    assert "labeled" in labeled
    assert "REQUEST_LABEL" in labeled


def test_wait_label_event_is_explicitly_recognized() -> None:
    script = GATE.read_text(encoding="utf-8")
    labeled = _function_body(script, "is_wait_label_event")

    assert "pull_request" in labeled
    assert "labeled" in labeled
    assert "REQUEST_LABEL" in labeled


def test_native_review_event_is_limited_to_initial_triggers() -> None:
    script = GATE.read_text(encoding="utf-8")
    native = _function_body(script, "is_native_review_event")

    assert "opened" in native
    assert "ready_for_review" in native
    assert "synchronize" not in native


def test_gate_detects_terminal_codex_failures() -> None:
    script = GATE.read_text(encoding="utf-8")
    failure = _function_body(script, "codex_failure_after")

    assert "reached your Codex usage limits for code reviews" in failure
    assert "Codex Review: Something went wrong" in failure
    assert "No automatic retry will be attempted" in failure


def test_gate_clears_one_shot_label_after_request() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert "clear_request_label" in request
    assert "@codex review" in request


def test_gate_rejects_stale_or_missing_revision_events() -> None:
    script = GATE.read_text(encoding="utf-8")
    wait = _function_body(script, "wait_for_review")

    assert "GITHUB_EVENT_PATH" in script
    assert ".pull_request.head.sha" in wait
    assert ".pull_request.base.sha" in wait
    assert "does not match current PR revision" in wait


def test_reusable_gate_preserves_context_and_pr_head_status_surface() -> None:
    action = Path("actions/codex-review-gate/action.yml").read_text(encoding="utf-8")
    script = GATE.read_text(encoding="utf-8")

    assert "review-context:" in action
    assert "CODEX_REVIEW_CONTEXT: ${{ inputs.review-context }}" in action
    assert "check-name:" in action
    assert "statuses:write" in action
    assert "CODEX_REVIEW_CHECK_NAME: ${{ inputs.check-name }}" in action
    assert "request-and-wait" in action
    assert 'REVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-${BASE_SHA}}"' in script
    assert '"repos/${REPO}/statuses/${HEAD_SHA}"' in script
    assert "publish_status pending" in script
    assert "complete_status success" in script


def test_codex_review_gate_shell_syntax() -> None:
    import subprocess

    subprocess.run(["bash", "-n", str(GATE)], check=True)
