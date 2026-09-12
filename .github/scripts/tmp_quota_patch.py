"""Temporary one-shot patcher for quota-aware Codex review governance."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path.cwd()
OLD_REF = "cd1f286222a286508c962288671c1f6c97b52d95"


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, count), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker not in text:
        target.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n", encoding="utf-8")


def patch_action_and_gate() -> None:
    action = "actions/codex-review-gate/action.yml"
    replace(
        action,
        "description: Request or require Codex review evidence for a pull-request HEAD.",
        "description: Request or require current-HEAD Codex review evidence while conserving review quota.",
    )
    replace(
        action,
        "  timeout-seconds:\n",
        "  request-label:\n"
        "    description: One-shot label authorizing a quota-consuming Codex review request.\n"
        "    required: false\n"
        "    default: \"codex:review\"\n"
        "  timeout-seconds:\n",
    )
    replace(
        action,
        "        CODEX_REVIEW_MODE: ${{ inputs.mode }}\n",
        "        CODEX_REVIEW_MODE: ${{ inputs.mode }}\n"
        "        CODEX_REVIEW_REQUEST_LABEL: ${{ inputs.request-label }}\n",
    )

    gate = "actions/codex-review-gate/codex-review-gate.sh"
    replace(
        gate,
        ': "${GITHUB_WORKFLOW_REF:?GITHUB_WORKFLOW_REF is required}"\n\nMODE="${CODEX_REVIEW_MODE:-wait}"',
        ': "${GITHUB_WORKFLOW_REF:?GITHUB_WORKFLOW_REF is required}"\n'
        ': "${GITHUB_EVENT_NAME:?GITHUB_EVENT_NAME is required}"\n'
        ': "${GITHUB_EVENT_PATH:?GITHUB_EVENT_PATH is required}"\n\n'
        'MODE="${CODEX_REVIEW_MODE:-wait}"',
    )
    replace(
        gate,
        'POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"\nSHORT_SHA=',
        'POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"\n'
        'REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"\n'
        'SHORT_SHA=',
    )
    replace(
        gate,
        'WORKFLOW_PATH="${WORKFLOW_PATH%@*}"\n\nis_codex_login=',
        'WORKFLOW_PATH="${WORKFLOW_PATH%@*}"\n'
        'EVENT_ACTION="$(jq -r \'.action // empty\' "$GITHUB_EVENT_PATH")"\n'
        'EVENT_LABEL="$(jq -r \'.label.name // empty\' "$GITHUB_EVENT_PATH")"\n\n'
        'is_codex_login=',
    )

    api_block = '''api_list() {
  local endpoint="$1"
  gh api --paginate \\
    -H "Accept: application/vnd.github+json" \\
    "$endpoint" \\
    --jq '.[]' | jq -s '.'
}
'''
    helpers = api_block + '''
is_request_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request_target" \\
    && "$EVENT_ACTION" == "labeled" \\
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}

is_wait_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \\
    && "$EVENT_ACTION" == "labeled" \\
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}

clear_request_label() {
  local encoded_label
  encoded_label="$(jq -rn --arg value "$REQUEST_LABEL" '$value | @uri')"
  if ! gh api --method DELETE \\
    "repos/${REPO}/issues/${PR_NUMBER}/labels/${encoded_label}" >/dev/null 2>&1; then
    echo "::warning::Unable to clear one-shot Codex review label ${REQUEST_LABEL}."
  fi
  return 0
}
'''
    replace(gate, api_block, helpers)

    current_workflow = '''current_workflow_id() {
  local run
  if ! run="$(gh api "repos/${REPO}/actions/runs/${GITHUB_RUN_ID}")"; then
    echo "::error::Unable to load the current governance workflow run."
    return 2
  fi
  jq -er '.workflow_id | tostring' <<<"$run" || {
    echo "::error::Current governance run is missing a workflow ID."
    return 2
  }
}
'''
    current_helpers = current_workflow + '''
current_run_created_at() {
  local run
  if ! run="$(gh api "repos/${REPO}/actions/runs/${GITHUB_RUN_ID}")"; then
    echo "::error::Unable to load the current governance workflow run."
    return 2
  fi
  jq -er '.created_at' <<<"$run" || {
    echo "::error::Current governance run is missing its server timestamp."
    return 2
  }
}
'''
    replace(gate, current_workflow, current_helpers)

    trigger = '''find_trigger_comment() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  find_bot_trigger_comment
  if [[ -z "$COMMENT_ID" ]]; then
    find_bootstrap_trigger_comment
  fi
}
'''
    failure_helpers = trigger + '''
codex_failure_after() {
  local since="$1"
  local comments body
  if ! comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"; then
    echo "::error::Unable to inspect Codex review-request failures."
    return 2
  fi
  body="$(
    jq -r \\
      --arg since "$since" \\
      "[
        .[]
        | select((${is_codex_login}))
        | select((.created_at // \\\"\\\") >= \\$since)
        | select(
            ((.body // \\\"\\\") | contains(\\\"reached your Codex usage limits for code reviews\\\"))
            or ((.body // \\\"\\\") | startswith(\\\"Codex Review: Something went wrong\\\"))
          )
        | .body
      ] | first // empty" \\
      <<<"$comments"
  )"
  [[ -n "$body" ]] || return 1
  if [[ "$body" == *"usage limits for code reviews"* ]]; then
    echo "::error::Codex code-review quota is unavailable. No automatic retry will be attempted; re-apply ${REQUEST_LABEL} after capacity returns."
  else
    echo "::error::Codex reported a review-request failure. No automatic retry will be attempted; re-apply ${REQUEST_LABEL} when ready."
  fi
  return 0
}
'''
    replace(gate, trigger, failure_helpers)

    old_request = '''request_review() {
  find_bot_trigger_comment
  if [[ -n "$COMMENT_ID" ]]; then
    echo "Codex review request for current HEAD ${SHORT_SHA} already exists."
    return 0
  fi
  local body response
  body="$(printf '@codex review\\n\\nAutomated AI Native Platform merge gate for `%s`.\\n%s\\n%s\\n' "$SHORT_SHA" "$MARKER" "$RUN_MARKER")"
  response="$(
    gh api --method POST \\
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \\
      -f body="$body"
  )"
  COMMENT_ID="$(jq -r '.id' <<<"$response")"
  echo "Requested Codex review for current HEAD ${SHORT_SHA}."
}
'''
    new_request = '''request_review() {
  find_bot_trigger_comment
  if [[ -n "$COMMENT_ID" ]]; then
    if codex_failure_after "$COMMENT_CREATED_AT" >/dev/null; then
      echo "Prior Codex request failed; this explicit ${REQUEST_LABEL} event authorizes one retry."
    else
      local failure_status=$?
      if [[ "$failure_status" -eq 1 ]]; then
        echo "A Codex review request for current HEAD ${SHORT_SHA} is still pending; not sending a duplicate and preserving quota."
        return 0
      fi
      return 2
    fi
  fi
  local body response
  body="$(printf '@codex review\\n\\nQuota-aware merge-ready AI Native Platform gate for `%s`.\\n%s\\n%s\\n' "$SHORT_SHA" "$MARKER" "$RUN_MARKER")"
  response="$(
    gh api --method POST \\
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \\
      -f body="$body"
  )"
  COMMENT_ID="$(jq -r '.id' <<<"$response")"
  echo "Requested one Codex review for merge-ready HEAD ${SHORT_SHA}."
}
'''
    replace(gate, old_request, new_request)

    old_tail = '''case "$MODE" in
  request)
    if has_matching_review; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA}."
      exit 0
    fi
    request_review
    exit 0
    ;;
  wait)
    ;;
  *)
    echo "::error::Unknown Codex review gate mode: ${MODE}."
    exit 2
    ;;
esac

echo "Waiting for clean Codex evidence for current HEAD ${SHORT_SHA}."
deadline=$((SECONDS + TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if has_clear_codex_evidence; then
    echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
    exit 0
  fi
  sleep "$POLL_SECONDS"
done

echo "::error::Codex has not completed a clean, fully resolved review of current HEAD ${SHORT_SHA}."
exit 1
'''
    new_tail = '''case "$MODE" in
  request)
    if ! is_request_label_event; then
      echo "Codex review request skipped. Apply ${REQUEST_LABEL} only when the PR is merge-ready."
      exit 0
    fi
    trap clear_request_label EXIT
    if has_matching_review; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA}."
      exit 0
    fi
    request_review
    exit 0
    ;;
  wait)
    ;;
  *)
    echo "::error::Unknown Codex review gate mode: ${MODE}."
    exit 2
    ;;
esac

if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  exit 0
fi

if ! is_wait_label_event; then
  echo "::error::Current HEAD ${SHORT_SHA} has no clean Codex review. Run deterministic CI and batch fixes first, then apply ${REQUEST_LABEL} once the PR is merge-ready."
  exit 1
fi

request_started_at="$(current_run_created_at)" || exit 2
echo "Waiting for one merge-ready Codex review of current HEAD ${SHORT_SHA}."
deadline=$((SECONDS + TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if has_clear_codex_evidence; then
    echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
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

echo "::error::Codex has not completed a clean, fully resolved review of current HEAD ${SHORT_SHA}. Re-apply ${REQUEST_LABEL} only after confirming the earlier request completed or failed."
exit 1
'''
    replace(gate, old_tail, new_tail)


def commit_action_revision() -> str:
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    run("git", "rm", ".github/workflows/tmp-quota-aware-codex-fix.yml")
    run("git", "rm", ".github/scripts/tmp_quota_patch.py")
    run("git", "add", "actions/codex-review-gate/action.yml", "actions/codex-review-gate/codex-review-gate.sh")
    run("git", "commit", "-m", "fix: make Codex review requests quota-aware")
    return run("git", "rev-parse", "HEAD", capture=True)


def repin_action(action_sha: str) -> None:
    for target in ROOT.rglob("*"):
        if not target.is_file() or ".git" in target.parts:
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD_REF in text:
            target.write_text(text.replace(OLD_REF, action_sha), encoding="utf-8")


def patch_workflow() -> None:
    workflow = ".github/workflows/codex-review.yml"
    replace(
        workflow,
        "  pull_request:\n    types: [opened, synchronize, reopened, ready_for_review, edited]\n"
        "  pull_request_target:\n    types: [opened, synchronize, reopened, ready_for_review, edited]\n",
        "  pull_request:\n    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
        "  pull_request_target:\n    types: [labeled]\n",
    )
    replace(
        workflow,
        "    if: github.event_name == 'pull_request_target' && github.event.pull_request.draft == false\n",
        "    if: github.event_name == 'pull_request_target' && github.event.action == 'labeled' && github.event.label.name == 'codex:review' && github.event.pull_request.draft == false\n",
    )
    replace(
        workflow,
        "      - name: Request Codex review of current HEAD\n",
        "      - name: Request one merge-ready Codex review\n",
    )
    replace(
        workflow,
        "          mode: request\n",
        "          mode: request\n          request-label: codex:review\n",
    )
    replace(
        workflow,
        "          mode: wait\n",
        "          mode: wait\n          request-label: codex:review\n",
    )


def patch_validator() -> None:
    ai = "ai_native.py"
    replace(
        ai,
        '    required = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}\n',
        '    required = {"opened", "synchronize", "reopened", "ready_for_review", "edited", "labeled"}\n',
    )

    dismissal_marker = '''def _event_runs_on_review_dismissal(workflow: Mapping[Any, Any]) -> bool:
'''
    label_helper = '''def _event_runs_only_on_label(workflow: Mapping[Any, Any], event_name: str) -> bool:
    """Return whether an event is restricted to label changes only."""
    events = _workflow_events_value(workflow)
    if not isinstance(events, Mapping) or event_name not in events:
        return False
    config = events[event_name]
    if not isinstance(config, Mapping):
        return False
    types = config.get("types")
    if isinstance(types, str):
        return types == "labeled"
    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):
        return {str(item) for item in types} == {"labeled"}
    return False


''' + dismissal_marker
    replace(ai, dismissal_marker, label_helper)

    wait_marker = '''def _uses_review_wait_events(job: Mapping[str, Any]) -> bool:
'''
    request_helper = '''def _uses_labeled_review_request(job: Mapping[str, Any]) -> bool:
    """Return whether request execution is bound to the one-shot review label."""
    condition = _normalize_condition(job.get("if"))
    event_guard = (
        "github.event_name == 'pull_request_target' && github.event.action == 'labeled' "
        "&& github.event.label.name == 'codex:review'"
    )
    draft_guard = f"{event_guard} && github.event.pull_request.draft == false"
    return condition in {event_guard, draft_guard}


''' + wait_marker
    replace(ai, wait_marker, request_helper)

    replace(
        ai,
        '        "mode": mode,\n',
        '        "mode": mode,\n        "request-label": "codex:review",\n',
    )

    old_events = '''    events = _workflow_events(workflow)
    for event_name in ("pull_request", "pull_request_target"):
        if event_name not in events:
            failures.append(f"missing {event_name} event")
        elif not _event_runs_on_required_pr_activities(workflow, event_name):
            failures.append(
                f"{event_name} must run on opened, synchronize, reopened, ready_for_review, and edited"
            )
'''
    new_events = '''    events = _workflow_events(workflow)
    if "pull_request" not in events:
        failures.append("missing pull_request event")
    elif not _event_runs_on_required_pr_activities(workflow, "pull_request"):
        failures.append(
            "pull_request must run on opened, synchronize, reopened, ready_for_review, edited, and labeled"
        )
    if "pull_request_target" not in events:
        failures.append("missing pull_request_target event")
    elif not _event_runs_only_on_label(workflow, "pull_request_target"):
        failures.append("pull_request_target must run only on labeled events")
'''
    replace(ai, old_events, new_events)
    replace(
        ai,
        '    if not _uses_event(request, "pull_request_target"):\n'
        '        failures.append("request job condition must canonically bind pull_request_target")\n',
        '    if not _uses_labeled_review_request(request):\n'
        '        failures.append("request job condition must bind only codex:review labeled events")\n',
    )


def patch_tests() -> None:
    tests = "tests/test_ai_review_governance_hardening.py"
    replace(
        tests,
        "on:\n  pull_request:\n  pull_request_target:\n  pull_request_review:\n",
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
        "  pull_request_target:\n    types: [labeled]\n  pull_request_review:\n",
    )
    replace(
        tests,
        "    if: github.event_name == 'pull_request_target'\n",
        "    if: github.event_name == 'pull_request_target' && github.event.action == 'labeled' && github.event.label.name == 'codex:review'\n",
    )
    replace(
        tests,
        "          mode: request\n",
        "          mode: request\n          request-label: codex:review\n",
    )
    replace(
        tests,
        "          mode: wait\n",
        "          mode: wait\n          request-label: codex:review\n",
    )
    replace(
        tests,
        '''def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace("  pull_request:\\n", "  pull_request:\\n    types: [synchronize]\\n", 1)
    _write_repository(tmp_path, workflow)
    assert any("opened, synchronize, reopened, ready_for_review, and edited" in item.message for item in _findings(tmp_path))
''',
        '''def test_review_gate_requires_all_pr_head_activities(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\\n",
        "    types: [opened, synchronize, reopened, ready_for_review, edited]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("opened, synchronize, reopened, ready_for_review, edited, and labeled" in item.message for item in _findings(tmp_path))
''',
    )
    replace(
        tests,
        '''def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request:\\n",
        "  pull_request:\\n    types: [opened, synchronize, reopened, ready_for_review]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("ready_for_review, and edited" in item.message for item in _findings(tmp_path))
''',
        '''def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\\n",
        "    types: [opened, synchronize, reopened, ready_for_review, labeled]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("edited, and labeled" in item.message for item in _findings(tmp_path))
''',
    )
    append_once(
        tests,
        "test_review_gate_restricts_writable_target_to_review_label",
        '''
def test_review_gate_restricts_writable_target_to_review_label(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request_target:\\n    types: [labeled]\\n",
        "  pull_request_target:\\n    types: [labeled, synchronize]\\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("pull_request_target must run only on labeled" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_explicit_codex_review_label_condition(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "github.event_name == 'pull_request_target' && github.event.action == 'labeled' && github.event.label.name == 'codex:review'",
        "github.event_name == 'pull_request_target'",
    )
    _write_repository(tmp_path, workflow)
    assert any("codex:review labeled events" in item.message for item in _findings(tmp_path))
''',
    )

    gate_tests = "tests/test_codex_review_gate.py"
    append_once(
        gate_tests,
        "test_review_requests_are_explicit_one_shot_and_quota_aware",
        '''
def test_review_requests_are_explicit_one_shot_and_quota_aware() -> None:
    script = GATE.read_text(encoding="utf-8")
    request = _function_body(script, "request_review")

    assert 'REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"' in script
    assert "is_request_label_event" in script
    assert "clear_request_label" in script
    assert "still pending; not sending a duplicate" in request
    assert "authorizes one retry" in request


def test_wait_path_fails_fast_until_merge_ready_label_is_applied() -> None:
    script = GATE.read_text(encoding="utf-8")

    assert "if ! is_wait_label_event; then" in script
    assert "Run deterministic CI and batch fixes first" in script


def test_quota_exhaustion_fails_without_automatic_retry() -> None:
    script = GATE.read_text(encoding="utf-8")
    failure = _function_body(script, "codex_failure_after")

    assert "reached your Codex usage limits for code reviews" in failure
    assert "No automatic retry will be attempted" in failure
''',
    )


def patch_docs() -> None:
    agents = "AGENTS.md"
    replace(
        agents,
        "- Never weaken evidence requirements merely to make a repository pass.\n",
        "- Never weaken evidence requirements merely to make a repository pass.\n"
        "- Treat Codex code review as asynchronous and quota-limited: batch fixes, rely on deterministic checks during iteration, request a fresh review only for a merge-ready exact HEAD/base checkpoint, and never auto-retry a failed or quota-exhausted review.\n",
    )

    docs = "docs/AI_REVIEW_GOVERNANCE.md"
    append_once(
        docs,
        "## Quota-aware review lifecycle",
        '''
## Quota-aware review lifecycle

Codex review is asynchronous and quota-limited. The reference workflow therefore treats a review request as a scarce merge-readiness operation rather than an every-push CI check. Deterministic CI, linting, tests, conformance, and security checks continue on every push. New commits or base changes invalidate stale review evidence but do not automatically spend another Codex review.

When the exact current HEAD/base pair is green and merge-ready, apply the one-shot `codex:review` label. Only that label may enter the writable `pull_request_target` request path; the request action clears the label after handling it. A current request is deduplicated, so re-labeling cannot create parallel duplicate requests. If Codex reports code-review quota exhaustion or a terminal request failure, the gate fails early and never retries automatically. Re-apply `codex:review` only after capacity returns or the failure condition is understood.

The read-only `codex-review` check still reevaluates every relevant HEAD/base transition and review dismissal. Without clean current evidence it fails fast during iteration instead of polling for the full review timeout; on the explicit merge-ready label event it waits for the single requested review. The merge invariant remains unchanged: exact current HEAD/base Codex evidence and zero unresolved Codex-authored review threads.
''',
    )

    changelog = "CHANGELOG.md"
    append_once(
        changelog,
        "Make Codex review quota-aware",
        '''
### Changed

- Make Codex review quota-aware: normal HEAD/base changes invalidate stale evidence without requesting another review; only the one-shot `codex:review` label can spend a review, pending requests are deduplicated, and quota/request failures never auto-retry.
''',
    )

    release = "RELEASE_NOTES.md"
    append_once(
        release,
        "Codex review requests are quota-aware",
        '''
Codex review requests are quota-aware. Normal pushes and base changes run deterministic checks and invalidate stale review evidence without creating a new Codex request. Apply the one-shot `codex:review` label only when the exact current HEAD/base pair is merge-ready. The gate removes the label after handling it, deduplicates pending requests, fails early on code-review quota exhaustion, and requires an explicit re-label after capacity returns.
''',
    )

    readme = "README.md"
    append_once(
        readme,
        "## Quota-aware Codex review",
        '''
## Quota-aware Codex review

Repositories opting into `evidence.paths.ai_review_workflow` should treat Codex review as an asynchronous, quota-limited merge gate rather than an every-push check. Deterministic CI continues on every commit. When the exact current HEAD/base pair is green and merge-ready, apply the one-shot `codex:review` label to request one review. New changes invalidate that evidence without automatically spending another review, and quota/request failures fail closed without automatic retries. See `docs/AI_REVIEW_GOVERNANCE.md`.
''',
    )


def create_review_label() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    check = subprocess.run(
        ["gh", "api", f"repos/{repo}/labels/codex%3Areview"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if check.returncode == 0:
        return
    run(
        "gh",
        "api",
        "--method",
        "POST",
        f"repos/{repo}/labels",
        "-f",
        "name=codex:review",
        "-f",
        "color=1D76DB",
        "-f",
        "description=One-shot request for a merge-ready current-HEAD/base Codex review",
    )


def validate() -> None:
    run("python", "-m", "pip", "install", "-e", ".[dev]")
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
    patch_action_and_gate()
    action_sha = commit_action_revision()
    repin_action(action_sha)
    patch_workflow()
    patch_validator()
    patch_tests()
    patch_docs()
    create_review_label()
    validate()
    run("git", "add", "-A")
    run("git", "commit", "-m", "fix: conserve Codex review quota at merge-ready checkpoints")
    run("git", "push", "origin", "HEAD:align/codex-governance")


if __name__ == "__main__":
    main()
