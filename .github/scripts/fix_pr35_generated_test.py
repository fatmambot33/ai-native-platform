"""Synchronize focused PR #35 regression fixtures with the remediated contract."""

from pathlib import Path


OLD_GROUP = (
    "codex-review-${{ github.event_name }}-"
    "${{ github.event.pull_request.number }}"
)
NEW_GROUP = OLD_GROUP + "-${{ github.event.pull_request.head.sha }}"


def main() -> None:
    """Update fixtures/assertions for HEAD-scoped concurrency and live review lookup."""
    for path in Path("tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        text = text.replace(OLD_GROUP, NEW_GROUP)
        text = text.replace(
            "assert 'has_native_matching_review \"\"' in body",
            'assert "event_review_is_live" in body',
        )
        path.write_text(text, encoding="utf-8")

    path = Path("tests/test_pr35_final_governance.py")
    text = path.read_text(encoding="utf-8")
    long_literal = f'    expected = "{NEW_GROUP}"\n'
    split_literal = '''    expected = (\n        "codex-review-${{ github.event_name }}-"\n        "${{ github.event.pull_request.number }}-"\n        "${{ github.event.pull_request.head.sha }}"\n    )\n'''
    if long_literal in text:
        text = text.replace(long_literal, split_literal, 1)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
