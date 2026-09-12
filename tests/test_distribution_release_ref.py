"""Release-ref regression coverage."""

from pathlib import Path


def test_distribution_release_ref_is_current() -> None:
    """The current distribution docs must not point back to v0.2.0."""
    assert "v0.2.0" not in Path("docs/DISTRIBUTION.md").read_text(encoding="utf-8")
