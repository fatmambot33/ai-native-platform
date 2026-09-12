"""Distribution ref guard."""

from pathlib import Path


def test_distribution_uses_current_ref() -> None:
    """Use the manifest-v2 validator release."""
    assert "v0.3.0" in Path("docs/DISTRIBUTION.md").read_text(encoding="utf-8")
