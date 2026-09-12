"""Cross-check shipped distribution references."""

from pathlib import Path


def test_shipped_distribution_references_match() -> None:
    """Template and docs must pin the same immutable validator release."""
    workflow = Path("templates/validate.yml").read_text(encoding="utf-8")
    docs = Path("docs/DISTRIBUTION.md").read_text(encoding="utf-8")

    assert "uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.3.0" in workflow
    assert "standard_ref: v0.3.0" in workflow
    assert "uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.3.0" in docs
    assert "standard_ref: v0.3.0" in docs
