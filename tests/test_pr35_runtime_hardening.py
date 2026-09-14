"""Focused regressions for PR #35 Codex gate runtime hardening."""

from __future__ import annotations

from pathlib import Path

PREFLIGHT = Path("actions/codex-review-gate/preflight.sh")


def test_revision_run_cache_refreshes_during_polling() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    block = script.split("revision_runs() {", 1)[1].split("\n}\n", 1)[0]

    assert "stat -c %Y" in block
    assert 'cache_ttl="$POLL_SECONDS"' in block
    assert "now - modified < cache_ttl" in block
    assert "head_sha=${HEAD_SHA}" in block
    assert "--paginate" not in block


def test_native_reaction_rejects_dismissed_review() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    reaction = script.split("has_native_clean_reaction() {", 1)[1].split("\n}\n", 1)[0]
    dismissed = script.split("has_dismissed_native_review_since() {", 1)[1].split("\n}\n", 1)[0]

    assert "has_dismissed_native_review_since" in reaction
    assert reaction.index("has_dismissed_native_review_since") < reaction.index("reactions=")
    assert "DISMISSED" in dismissed
    assert ".commit_id" in dismissed
    assert "return 2" in dismissed


def test_success_revalidates_live_head_and_base() -> None:
    script = PREFLIGHT.read_text(encoding="utf-8")
    verify = script.split("verify_live_revision() {", 1)[1].split("\n}\n", 1)[0]
    complete = script.split("complete_status() {", 1)[1].split("\n}\n", 1)[0]

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
