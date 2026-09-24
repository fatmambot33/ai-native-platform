"""Regression tests for inheritance schema discovery."""

from pathlib import Path

from ai_native_platform.inheritance import _schema_path


def test_schema_path_prefers_packaged_schema_over_adjacent_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    """Installed validation must not trust a repository-adjacent schema copy."""
    package_root = tmp_path / "ai_native_platform"
    packaged = package_root / "schemas" / "ai-native-derived.schema.json"
    adjacent = tmp_path / "schemas" / "ai-native-derived.schema.json"
    packaged.parent.mkdir(parents=True)
    adjacent.parent.mkdir(parents=True)
    packaged.write_text('{"source": "package"}', encoding="utf-8")
    adjacent.write_text('{"source": "adjacent"}', encoding="utf-8")
    monkeypatch.setattr(
        "ai_native_platform.inheritance.__file__",
        str(package_root / "inheritance.py"),
    )

    assert _schema_path() == packaged
