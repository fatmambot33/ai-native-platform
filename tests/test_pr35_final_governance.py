"""Final focused governance regressions for PR #35."""

from __future__ import annotations

from pathlib import Path

from ai_native import TRUSTED_AI_REVIEW_GATE_REFS

SUPERSEDED_GATE_REF = "0c4f68f62abb426ba80d0d1bb36356c3468f5534"


def test_canonical_workflow_uses_only_current_trusted_gate() -> None:
    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")
    assert SUPERSEDED_GATE_REF not in TRUSTED_AI_REVIEW_GATE_REFS
    assert f"@{SUPERSEDED_GATE_REF}" not in workflow
    assert len(TRUSTED_AI_REVIEW_GATE_REFS) == 1
    trusted = next(iter(TRUSTED_AI_REVIEW_GATE_REFS))
    assert workflow.count(f"@{trusted}") == 2


def test_native_review_reuse_is_bound_to_current_base_event_and_live_state() -> None:
    gate = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    preflight = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")
    assert "types: [submitted, dismissed]" in workflow
    assert "EVENT_BASE_SHA=" in gate
    assert "EVENT_REVIEW_COMMIT_SHA=" in gate
    assert "is_current_base_native_review_submission()" in gate
    assert '"$EVENT_BASE_SHA" == "$BASE_SHA"' in gate
    assert '"$EVENT_REVIEW_COMMIT_SHA" == "$HEAD_SHA"' in gate
    body = preflight.split("has_any_native_clear_codex_evidence() {", 1)[1].split("\n}\n", 1)[0]
    assert "is_current_base_native_review_submission" in body
    assert "event_review_id=" in body
    assert r'.id == \$review_id' in body
    assert r'(.state // \"\") != \"DISMISSED\"' in body
    assert r'(.commit_id // \"\") == \$head' in body
    assert "has_native_clean_reaction" not in body


def test_release_records_and_release_policy_are_codeowner_governed() -> None:
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    assert "/CHANGELOG.md @fatmambot33" in codeowners
    assert "/RELEASE_NOTES.md @fatmambot33" in codeowners
    assert "/docs/RELEASE.md @fatmambot33" in codeowners
    assert '"CHANGELOG.md"' in validator
    assert '"RELEASE_NOTES.md"' in validator
    assert '"docs/RELEASE.md"' in validator



def test_security_and_distribution_evidence_are_codeowner_governed() -> None:
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")

    assert "/docs/SECURITY_EVIDENCE.md @fatmambot33" in codeowners
    assert "/docs/DISTRIBUTION.md @fatmambot33" in codeowners
    assert '"docs/SECURITY_EVIDENCE.md"' in validator
    assert '"docs/DISTRIBUTION.md"' in validator
