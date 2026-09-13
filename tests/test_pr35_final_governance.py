import inspect
from pathlib import Path

import ai_native


def test_canonical_gate_rejects_nonempty_check_name() -> None:
    source = inspect.getsource(ai_native._gate_ref)
    assert 'inputs.get("check-name") not in (None, "")' in source


def test_native_review_thread_status_is_captured_in_else_branch() -> None:
    text = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    segment = text.split("has_any_native_clear_codex_evidence()", 1)[1]
    segment = segment.split("has_native_clean_reaction()", 1)[0]
    assert "else\n    local thread_status=$?" in segment


def test_trusted_gate_ref_is_finalized_core_commit() -> None:
    assert ai_native.TRUSTED_AI_REVIEW_GATE_REFS == frozenset(
        {"70a27f1691c870f1f5423698b2864edd96fee98c"}
    )


def test_native_review_reuse_is_bound_to_current_base_event() -> None:
    gate = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")
    assert "types: [submitted, dismissed]" in workflow
    assert "EVENT_BASE_SHA=" in gate
    assert "EVENT_REVIEW_COMMIT_SHA=" in gate
    assert "is_current_base_native_review_submission()" in gate
    assert '"$EVENT_BASE_SHA" == "$BASE_SHA"' in gate
    assert '"$EVENT_REVIEW_COMMIT_SHA" == "$HEAD_SHA"' in gate
    body = gate.split("has_any_native_clear_codex_evidence() {", 1)[1].split("\n}", 1)[0]
    assert "is_current_base_native_review_submission" in body
    assert "has_any_native_matching_review" not in body


def test_release_records_are_codeowner_governed() -> None:
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    assert "/CHANGELOG.md @fatmambot33" in codeowners
    assert "/RELEASE_NOTES.md @fatmambot33" in codeowners
    assert '"CHANGELOG.md",' in validator
    assert '"RELEASE_NOTES.md",' in validator
