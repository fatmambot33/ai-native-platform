"""Cross-check shipped distribution references."""

from pathlib import Path


def test_shipped_distribution_references_match() -> None:
    """Template and docs must point at the same immutable release."""
    workflow = Path("templates/validate.yml").read_text(encoding="utf-8")
    docs = Path("docs/DISTRIBUTION.md").read_text(encoding="utf-8")

    assert "@v0.3.0" in workflow
    assert "@v0.3.0" in docs
