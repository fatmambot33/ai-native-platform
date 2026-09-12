"""Current release pin guard."""

from pathlib import Path


def test_current_validator_pin() -> None:
    """Keep the starter validation workflow on v0.3.0."""
    assert "@v0.3.0" in Path("templates/validate.yml").read_text(encoding="utf-8")
