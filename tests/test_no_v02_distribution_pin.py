"""Guard against reintroducing the stale distribution pin."""

from pathlib import Path


def test_bundled_workflow_does_not_pin_v020() -> None:
    """The bundled workflow must understand manifest v2."""
    assert "@v0.2.0" not in Path("templates/validate.yml").read_text(encoding="utf-8")
