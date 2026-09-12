"""Distribution-version contract regression coverage."""

from pathlib import Path


def test_distribution_pin_matches_manifest_v2_release() -> None:
    """The shipped reusable workflow must use the v0.3 validator line."""
    workflow = Path("templates/validate.yml").read_text(encoding="utf-8")

    assert "@v0.3.0" in workflow
