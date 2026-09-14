"""Focused regressions for PR #35 Codex gate runtime hardening."""

from __future__ import annotations

from pathlib import Path

PREFLIGHT = Path("actions/codex-review-gate/preflight.sh")


def _block(script: str, function_name: str) -> str:
    """Return one shell function body from the preflight wrapper."""
    return script.split(f"{function_name}() {{", 1)[1].split("\n}\n", 1)[0]


def test_revision_run_cache_refreshes_and_paginates_filtered_history() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = _block(script, "revision_runs")

    assert "stat -c %Y" in block
    assert 'cache_ttl="$POLL_SECONDS"' in block
    assert "now - modified < cache_ttl" in block
    assert "head_sha=${HEAD_SHA}" in block
    assert "--paginate" in block
    assert "--jq '.workflow_runs[]'" in block
    assert "jq -s '.'" in block


def test_native_reaction_rejects_dismissed_review() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    reaction = _block(script, "has_native_clean_reaction")
    dismissed = _block(script, "has_dismissed_native_review_since")

    assert "has_dismissed_native_review_since" in reaction
    assert reaction.index("has_dismissed_native_review_since") < reaction.index("reactions=")
    assert "DISMISSED" in dismissed
    assert ".commit_id" in dismissed
    assert "return 2" in dismissed


def test_terminal_failures_must_match_current_revision_marker() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = _block(script, "codex_failure_after")

    assert '--arg marker "$MARKER"' in block
    assert 'contains($marker)' in block
    assert 'select((.created_at // "") >= $since)' in block


def test_request_review_propagates_dismissal_lookup_errors() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = _block(script, "request_review")

    assert "dismissal_status=$?" in block
    assert 'if [[ "$dismissal_status" -ne 1 ]]' in block
    assert "Unable to prove whether the matching Codex review was dismissed" in block
    assert block.index("dismissal_status=$?") < block.index("codex_failure_after")


def test_request_and_wait_clears_one_shot_label_on_every_exit() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = _block(script, "on_exit_with_request_label")

    assert "clear_request_label || true" in block
    assert 'if [[ "$MODE" == "request-and-wait" ]]' in script
    assert "trap on_exit_with_request_label EXIT" in script


def test_request_runtime_requires_non_draft_pr() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = _block(script, "is_request_label_event")

    assert ".pull_request.draft // true" in block
    assert '"$draft" == "false"' in block
    assert "non-draft PR" in script


def test_success_revalidates_live_head_and_base() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    verify = _block(script, "verify_live_revision")
    complete = _block(script, "complete_status")

    assert '"repos/${REPO}/pulls/${PR_NUMBER}"' in verify
    assert ".head.sha" in verify
    assert ".base.sha" in verify
    assert '"$live_head" != "$HEAD_SHA"' in verify
    assert '"$live_base" != "$BASE_SHA"' in verify
    assert 'if [[ "$state" == "success" ]]' in complete
    assert "verify_live_revision" in complete


def test_preflight_executes_canonical_gate_with_runtime_overrides() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")

    assert "source <(sed '/^case \"$MODE\" in/,$d' \"$GATE_SCRIPT\")" in script
    assert "source <(sed -n '/^case \"$MODE\" in/,$p' \"$GATE_SCRIPT\")" in script
    assert "exec bash \"$GITHUB_ACTION_PATH/codex-review-gate.sh\"" not in script
