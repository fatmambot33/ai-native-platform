"""Shared pytest setup for repository-evidence fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _protect_temporary_review_workflows(request: pytest.FixtureRequest) -> None:
    """Give temporary repositories the canonical review-workflow ownership rule."""
    if "tmp_path" not in request.fixturenames:
        return
    tmp_path = request.getfixturevalue("tmp_path")
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.parent.mkdir(parents=True, exist_ok=True)
    codeowners.write_text("/.github/workflows/** @repository-owner\n", encoding="utf-8")
