"""Regression coverage for shipped reusable-workflow pins."""

from pathlib import Path


def test_bundled_validation_workflow_pins_v030() -> None:
    """The manifest-v2 starter must call a validator that understands manifest v2."""
    text = Path("templates/validate.yml").read_text(encoding="utf-8")

    assert "fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.3.0" in text
