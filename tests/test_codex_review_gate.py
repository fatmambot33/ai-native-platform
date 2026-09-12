"""Tests for the reusable Codex review gate action."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "actions" / "codex-review-gate" / "action.yml"
SCRIPT = ROOT / "actions" / "codex-review-gate" / "codex-review-gate.sh"


def test_codex_review_gate_shell_syntax() -> None:
    """Keep the reusable gate syntactically valid Bash."""
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_codex_review_action_wires_review_context() -> None:
    """Expose and forward the optional context key to the gate script."""
    action = ACTION.read_text(encoding="utf-8")

    assert "review-context:" in action
    assert "CODEX_REVIEW_CONTEXT: ${{ inputs.review-context }}" in action


def test_codex_review_gate_requires_trusted_request_markers() -> None:
    """Only accept context markers created by the trusted Actions bot."""
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'select((.user.login // "") == "github-actions[bot]")' in script


def test_context_requires_a_context_specific_request(tmp_path: Path) -> None:
    """Do not accept an old HEAD review before a context request exists."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "gh.log"
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$GH_TEST_LOG"
if [[ "$*" == *'/pulls/42/reviews?per_page=100'* ]]; then
  cat <<'JSON'
{
  "user": {"login": "chatgpt-codex-connector[bot]"},
  "state": "COMMENTED",
  "commit_id": "abc123",
  "submitted_at": "2026-09-12T09:00:00Z"
}
JSON
elif [[ "$*" == *'/issues/42/comments?per_page=100'* ]]; then
  exit 0
elif [[ "$*" == *'--method POST'* ]]; then
  printf '%s\\n' '{"id":123,"created_at":"2026-09-12T10:00:00Z"}'
else
  exit 0
fi
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "GH_TEST_LOG": str(log),
            "GH_TOKEN": "test-token",
            "REPO": "owner/repo",
            "PR_NUMBER": "42",
            "HEAD_SHA": "abc123",
            "CODEX_REVIEW_CONTEXT": "base456",
            "CODEX_REVIEW_MODE": "request",
        }
    )

    subprocess.run(["bash", str(SCRIPT)], check=True, env=env)

    calls = log.read_text(encoding="utf-8")
    assert "--method POST" in calls
