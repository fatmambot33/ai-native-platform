import inspect
from pathlib import Path

import ai_native


def test_canonical_gate_rejects_nonempty_check_name() -> None:
    source = inspect.getsource(ai_native._gate_ref)
    assert 'inputs.get("check-name") not in (None, "")' in source


def test_native_review_thread_status_is_captured_in_else_branch() -> None:
    text = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(
        encoding="utf-8"
    )
    segment = text.split("has_any_native_clear_codex_evidence()", 1)[1]
    segment = segment.split("has_native_clean_reaction()", 1)[0]
    assert "else\n    local thread_status=$?" in segment
