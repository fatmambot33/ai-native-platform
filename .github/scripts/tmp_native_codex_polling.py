"""One-shot patcher for quota-safe native Codex review polling."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path.cwd()
OLD_REF = "fce175de5b4252a748de4e29176ab3eea4f3c717"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int = -1) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"expected text missing from {path}: {old[:100]!r}")
    write(path, text.replace(old, new, count))


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def patch_gate() -> None:
    path = "actions/codex-review-gate/codex-review-gate.sh"
    replace(
        path,
        '''is_wait_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \\
    && "$EVENT_ACTION" == "labeled" \\
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}
''',
        '''is_wait_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \\
    && "$EVENT_ACTION" == "labeled" \\
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}

is_native_review_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \\
    && ( "$EVENT_ACTION" == "opened" || "$EVENT_ACTION" == "ready_for_review" ) ]]
}
''',
    )
    marker = '''has_trigger_clean_reaction() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  if ! find_bot_trigger_comment; then
    return 2
  fi
  [[ -n "$COMMENT_ID" ]] || return 1
  local reactions
  reactions="$(api_list "repos/${REPO}/issues/comments/${COMMENT_ID}/reactions?per_page=100")"
  jq -e \\
    "any(.[]; (${is_codex_login}) and .content == \\"+1\\")" \\
    <<<"$reactions" >/dev/null
}
'''
    native = marker + '''

has_native_matching_review() {
  local since="$1"
  local reviews
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \\
    --arg head "$HEAD_SHA" \\
    --arg since "$since" \\
    "any(.[]; (${is_codex_login}) and ((.state // \\"\\") != \\"DISMISSED\\") and ((.commit_id // \\"\\") == \\$head) and ((.submitted_at // \\"\\") >= \\$since))" \\
    <<<"$reviews" >/dev/null
}

has_native_clean_reaction() {
  local since="$1"
  local reactions
  reactions="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/reactions?per_page=100")"
  jq -e \\
    --arg since "$since" \\
    "any(.[]; (${is_codex_login}) and .content == \\"+1\\" and ((.created_at // \\"\\") >= \\$since))" \\
    <<<"$reactions" >/dev/null
}

has_native_clear_codex_evidence() {
  local since="$1"
  if has_native_matching_review "$since" || has_native_clean_reaction "$since"; then
    if has_unresolved_codex_threads; then
      echo "Native Codex evidence exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
      return 1
    else
      local thread_status=$?
      if [[ "$thread_status" -eq 1 ]]; then
        return 0
      fi
      echo "::error::Unable to prove that all Codex review threads are resolved for current HEAD ${SHORT_SHA}."
      return 1
    fi
  fi
  return 1
}
'''
    replace(path, marker, native)

    tail_anchor = '''if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  exit 0
fi

if ! is_wait_label_event; then
'''
    tail_new = '''if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  exit 0
fi

if is_native_review_event; then
  request_started_at="$(current_run_created_at)" || exit 2
  echo "Waiting for the native Codex review of current HEAD ${SHORT_SHA}; no duplicate request will be sent."
  deadline=$((SECONDS + TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if has_native_clear_codex_evidence "$request_started_at"; then
      echo "Native Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
      exit 0
    fi
    if codex_failure_after "$request_started_at"; then
      exit 1
    else
      failure_status=$?
      if [[ "$failure_status" -eq 2 ]]; then
        exit 2
      fi
    fi
    sleep "$POLL_SECONDS"
  done
  echo "::error::Native Codex review did not complete cleanly for current HEAD ${SHORT_SHA}."
  echo "::error::Apply ${REQUEST_LABEL} only as an explicit fallback after confirming the native review ended."
  exit 1
fi

if ! is_wait_label_event; then
'''
    replace(path, tail_anchor, tail_new)


def commit_action_revision() -> str:
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "add", "actions/codex-review-gate/codex-review-gate.sh")
    run("git", "commit", "-m", "fix: reuse native Codex review without duplicate request")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def repin(new_ref: str) -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    for raw in tracked:
        if not raw:
            continue
        path = Path(raw.decode())
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD_REF in text:
            path.write_text(text.replace(OLD_REF, new_ref), encoding="utf-8")


def patch_docs() -> None:
    path = "docs/AI_REVIEW_GOVERNANCE.md"
    text = read(path)
    anchor = """Because Codex review is asynchronous and quota-limited, deterministic CI should carry the inner development loop. Batch fixes and request Codex only at merge-ready checkpoints. The gate treats quota exhaustion and terminal Codex errors as explicit failures and never retries automatically; re-apply `codex:review` only after confirming capacity or resolving the earlier failure.
"""
    replacement = anchor + """
When repository-level Codex automatic review is enabled, opening a non-draft PR or marking a draft ready already starts Codex. The wait job reuses that native review and polls evidence created after the trusted current workflow run timestamp, including an exact-HEAD submitted review or a clean PR reaction. It never emits a second `@codex review` request for that checkpoint. The `codex:review` label remains an explicit fallback/retry mechanism when no native review is available or an earlier request ended terminally.
"""
    if anchor not in text:
        raise RuntimeError("quota lifecycle documentation anchor missing")
    write(path, text.replace(anchor, replacement, 1))


def patch_tests() -> None:
    path = "tests/test_codex_review_gate.py"
    text = read(path)
    addition = r'''


def test_ready_for_review_reuses_native_codex_evidence() -> None:
    script = GATE.read_text(encoding="utf-8")
    native_event = _function_body(script, "is_native_review_event")
    native_review = _function_body(script, "has_native_matching_review")
    native_reaction = _function_body(script, "has_native_clean_reaction")

    assert "ready_for_review" in native_event
    assert "opened" in native_event
    assert "commit_id" in native_review
    assert "$head" in native_review
    assert "submitted_at" in native_review
    assert "$since" in native_review
    assert "issues/${PR_NUMBER}/reactions?per_page=100" in native_reaction
    assert ".content == \\"+1\\"" in native_reaction
    assert "created_at" in native_reaction
    assert "$since" in native_reaction
    assert "no duplicate request will be sent" in script
'''
    if "test_ready_for_review_reuses_native_codex_evidence" not in text:
        text += addition
    write(path, text)


def cleanup_script() -> None:
    run("git", "rm", "-f", ".github/scripts/tmp_native_codex_polling.py")


def validate() -> None:
    run("python", "-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]")
    run("ruff", "format", "tests/test_codex_review_gate.py")
    run("ruff", "check", ".")
    run("pytest")
    run("python", "validator/validate_standard.py")
    run(
        "python",
        "-m",
        "ai_native",
        "validate",
        "fixtures/consumer-repository/AI_NATIVE_PLATFORM.yaml",
        "--root",
        "fixtures/consumer-repository",
    )
    run("bash", "-n", "actions/codex-review-gate/codex-review-gate.sh")
    run("python", "-m", "build")
    run("git", "diff", "--check")


def main() -> None:
    patch_gate()
    action_sha = commit_action_revision()
    repin(action_sha)
    patch_docs()
    patch_tests()
    cleanup_script()
    validate()

    run(
        "git",
        "add",
        "-A",
        "--",
        ":!.github/workflows/codex-review.yml",
        ":!.github/workflows/tmp-native-codex-polling.yml",
    )
    run("git", "commit", "-m", "fix: poll native Codex review at merge-ready transition")
    run("git", "push", "origin", "HEAD:align/codex-governance")
    print(f"ACTION_SHA={action_sha}")


if __name__ == "__main__":
    main()
