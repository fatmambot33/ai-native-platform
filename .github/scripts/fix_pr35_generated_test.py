"""Synchronize focused PR #35 regression fixtures with the remediated contract."""

from pathlib import Path


OLD_GROUP = (
    "codex-review-${{ github.event_name }}-"
    "${{ github.event.pull_request.number }}"
)
HEAD_PART = "${{ github.event.pull_request.head.sha }}"
NEW_GROUP = OLD_GROUP + f"-{HEAD_PART}"
DOUBLE_HEAD_GROUP = NEW_GROUP + f"-{HEAD_PART}"


def _wrap_yaml_group(text: str) -> str:
    """Wrap the long YAML concurrency scalar without changing its value."""
    old = f"  group: {NEW_GROUP}\n"
    new = (
        '  group: "codex-review-${{ github.event_name }}-\\\n'
        '    ${{ github.event.pull_request.number }}-\\\n'
        '    ${{ github.event.pull_request.head.sha }}"\n'
    )
    return text.replace(old, new)


def _mark_long_source_literals(text: str) -> str:
    """Mark unavoidable long source literals while leaving YAML strings untouched."""
    lines = []
    for line in text.splitlines(keepends=True):
        if NEW_GROUP in line and "group:" not in line and "# noqa: E501" not in line:
            line = line.rstrip("\n") + "  # noqa: E501\n"
        lines.append(line)
    return "".join(lines)


def main() -> None:
    """Update fixtures/assertions for HEAD-scoped concurrency and live review lookup."""
    for path in Path("tests").glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        text = text.replace(DOUBLE_HEAD_GROUP, NEW_GROUP)
        text = text.replace(OLD_GROUP, NEW_GROUP)
        text = text.replace(DOUBLE_HEAD_GROUP, NEW_GROUP)
        text = text.replace(
            "assert 'has_native_matching_review \"\"' in body",
            'assert "event_review_is_live" in body',
        )
        text = _wrap_yaml_group(text)
        text = _mark_long_source_literals(text)
        path.write_text(text, encoding="utf-8")

    path = Path("tests/test_pr35_final_governance.py")
    text = path.read_text(encoding="utf-8")
    long_literal = f'    expected = "{NEW_GROUP}"  # noqa: E501\n'
    split_literal = '''    expected = (\n        "codex-review-${{ github.event_name }}-"\n        "${{ github.event.pull_request.number }}-"\n        "${{ github.event.pull_request.head.sha }}"\n    )\n'''
    if long_literal in text:
        text = text.replace(long_literal, split_literal, 1)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
