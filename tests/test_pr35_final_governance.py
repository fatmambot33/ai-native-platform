import inspect
from pathlib import Path

from ai_native import TRUSTED_AI_REVIEW_GATE_REFS

REMEDIATED_GATE_REF = "0c4f68f62abb426ba80d0d1bb36356c3468f5534"


def test_canonical_gate_rejects_nonempty_check_name() -> None:
    import ai_native

    source = inspect.getsource(ai_native._gate_ref)
    assert 'inputs.get("check-name") not in (None, "")' in source


def test_native_review_thread_status_is_captured_in_else_branch() -> None:
    text = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    segment = text.split("has_any_native_clear_codex_evidence()", 1)[1]
    segment = segment.split("has_native_clean_reaction()", 1)[0]
    assert "else\n      thread_status=$?" in segment


def test_trusted_gate_ref_is_only_remediated_commit() -> None:
    assert TRUSTED_AI_REVIEW_GATE_REFS == frozenset({REMEDIATED_GATE_REF})
    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")
    assert workflow.count(f"@{REMEDIATED_GATE_REF}") == 2


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


def test_release_records_and_release_policy_are_codeowner_governed() -> None:
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    assert "/CHANGELOG.md @fatmambot33" in codeowners
    assert "/RELEASE_NOTES.md @fatmambot33" in codeowners
    assert "/docs/RELEASE.md @fatmambot33" in codeowners
    assert '"CHANGELOG.md",' in validator
    assert '"RELEASE_NOTES.md",' in validator
    assert '"docs/RELEASE.md",' in validator


def test_workflow_event_key_validation_preserves_literal_spelling() -> None:
    import ai_native

    source = inspect.getsource(ai_native._workflow_top_level_event_key_is_valid)
    workflow_validation = inspect.getsource(ai_native._single_ai_review_workflow_findings)
    assert 'keys.count("on") == 1' in source
    assert '"true" not in keys' in source
    assert "yaml.compose" in source
    assert "_workflow_top_level_event_key_is_valid(workflow_text)" in workflow_validation


def test_review_request_condition_requires_non_draft_guard() -> None:
    import ai_native

    source = inspect.getsource(ai_native._uses_labeled_review_request)
    assert "github.event.pull_request.draft == false" in source
    assert "return condition == draft_guard" in source
    assert "condition in {event_guard, draft_guard}" not in source
