"""Regression tests for the canonical current-HEAD Codex review gate."""

from __future__ import annotations

from pathlib import Path

import yaml

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
    assert "if ! is_request_label_event" in script


def test_gate_does_not_auto_retry_review_requests() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert "still pending; preserving quota" in request
    assert "No automatic retry will be attempted" in script


def test_gate_validates_request_comments_without_mutating_them() -> None:
    script = GATE.read_text(encoding="utf-8")

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

    assert "clear_request_label" in script
    assert "trap clear_request_label EXIT" in script
    assert "@codex review" in script


def test_gate_binds_request_provenance_to_pr_revision() -> None:
    script = GATE.read_text(encoding="utf-8")
    trusted = _function_body(script, "trusted_request_run")

    assert ".head.sha" in trusted
    assert ".base.sha" in trusted
    assert "$head" in trusted
    assert "$base" in trusted


def test_reusable_gate_preserves_context_and_pr_head_status_surface() -> None:
    action = Path("actions/codex-review-gate/action.yml").read_text(encoding="utf-8")
    action_data = yaml.safe_load(action)
    script = GATE.read_text(encoding="utf-8")

    assert action_data["inputs"]["base-sha"]["required"] is True
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


def test_request_and_wait_mode_polls_after_requesting_review() -> None:
    script = GATE.read_text(encoding="utf-8")
    request_and_wait = script.split("  request-and-wait)", maxsplit=1)[1].split(
        "  *)", maxsplit=1
    )[0]

    assert "request_review" in request_and_wait
    assert "Waiting for the requested Codex review" in request_and_wait
    assert "while (( SECONDS < deadline ))" in request_and_wait
    assert "has_clear_codex_evidence" in request_and_wait
    assert "codex_failure_after \"$request_started_at\"" in request_and_wait


def test_codex_review_gate_shell_syntax() -> None:
    import subprocess

    subprocess.run(["bash", "-n", str(GATE)], check=True)



def test_gate_removes_unverifiable_collaborator_bootstrap() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("find_trigger_comment() {", 1)[1].split("}\n", 1)[0]
    assert "find_bot_trigger_comment" in block
    assert "find_bootstrap_trigger_comment" not in block


def test_dismissed_review_invalidates_clean_request_reaction() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("has_trigger_clean_reaction() {", 1)[1].split("\n}\n", 1)[0]
    assert "has_dismissed_matching_review" in block
    assert block.index("has_dismissed_matching_review") < block.index("reactions=")


def test_gate_reuses_late_native_review_before_fallback_request() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("request_review() {", 1)[1].split("\n}\n", 1)[0]
    assert "has_any_native_clear_codex_evidence" in block
    assert block.index("has_any_native_clear_codex_evidence") < block.index("gh api --method POST")


def test_native_evidence_is_reusable_for_exact_revision() -> None:
    script = GATE.read_text(encoding="utf-8")
    reusable = _function_body(script, "has_any_native_clear_codex_evidence")
    assert "revision_activation_created_at" in reusable
    assert "has_trusted_native_review_run" in reusable
    assert "has_native_matching_review" in reusable


def test_native_clean_reaction_remains_revision_bound_evidence() -> None:
    script = GATE.read_text(encoding="utf-8")
    reusable = _function_body(script, "has_any_native_clear_codex_evidence")
    assert "has_single_base_for_head" in reusable
    assert "has_native_clean_reaction" in reusable


def test_dismissal_query_errors_fail_closed() -> None:
    script = GATE.read_text(encoding="utf-8")
    reaction = _function_body(script, "has_trigger_clean_reaction")
    assert "dismissal_status" in reaction
    assert "Unable to prove marker-backed review evidence is not dismissed" in reaction
