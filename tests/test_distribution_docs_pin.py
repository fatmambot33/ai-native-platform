"""Regression coverage for documented distribution pins."""

from pathlib import Path


def test_distribution_docs_pin_v030() -> None:
    """Distribution guidance must match the manifest-v2 validator release."""
    text = Path("docs/DISTRIBUTION.md").read_text(encoding="utf-8")

    assert "@v0.3.0" in text
    assert "@v0.2.0" not in text
