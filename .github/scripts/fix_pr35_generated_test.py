"""Normalize formatting in the temporary generated PR #35 regression."""

from pathlib import Path


def main() -> None:
    """Split the long concurrency literal without changing its value."""
    path = Path("tests/test_pr35_final_governance.py")
    text = path.read_text(encoding="utf-8")
    old = '    expected = "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}-${{ github.event.pull_request.head.sha }}"\n'
    new = '''    expected = (\n        "codex-review-${{ github.event_name }}-"\n        "${{ github.event.pull_request.number }}-"\n        "${{ github.event.pull_request.head.sha }}"\n    )\n'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit("expected concurrency regression literal not found")
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
