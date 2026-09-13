"""Temporary deterministic reconciliation for PR #35."""

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


action = '''name: Codex current-HEAD review gate
description: Request or require current-HEAD Codex review evidence while conserving review quota.

inputs:
  token:
    description: GitHub token. Request mode needs issues:write; PR-head status reporting needs statuses:write.
    required: true
  pr-number:
    description: Pull request number.
    required: true
  head-sha:
    description: Current pull request HEAD SHA.
    required: true
  base-sha:
    description: Current pull request base SHA for exact revision binding.
    required: false
    default: ""
  review-context:
    description: Optional context key for reusable callers; defaults to base-sha when omitted.
    required: false
    default: ""
  mode:
    description: One of request, wait, or request-and-wait.
    required: false
    default: wait
  request-label:
    description: One-shot label authorizing a quota-consuming Codex review request.
    required: false
    default: "codex:review"
  check-name:
    description: Optional commit-status context to publish directly on the pull-request HEAD. Intended for trusted workflows with statuses:write.
    required: false
    default: ""
  timeout-seconds:
    description: Maximum time to wait for Codex.
    required: false
    default: "1800"
  poll-seconds:
    description: Poll interval while waiting for Codex.
    required: false
    default: "60"

runs:
  using: composite
  steps:
    - name: Run Codex current-HEAD review gate
      shell: bash
      env:
        GH_TOKEN: ${{ inputs.token }}
        REPO: ${{ github.repository }}
        PR_NUMBER: ${{ inputs.pr-number }}
        HEAD_SHA: ${{ inputs.head-sha }}
        BASE_SHA: ${{ inputs.base-sha }}
        CODEX_REVIEW_CONTEXT: ${{ inputs.review-context }}
        CODEX_REVIEW_MODE: ${{ inputs.mode }}
        CODEX_REVIEW_REQUEST_LABEL: ${{ inputs.request-label }}
        CODEX_REVIEW_CHECK_NAME: ${{ inputs.check-name }}
        CODEX_REVIEW_TIMEOUT_SECONDS: ${{ inputs.timeout-seconds }}
        CODEX_REVIEW_POLL_SECONDS: ${{ inputs.poll-seconds }}
      run: bash "$GITHUB_ACTION_PATH/codex-review-gate.sh"
'''
Path("actions/codex-review-gate/action.yml").write_text(action, encoding="utf-8")

path = Path("actions/codex-review-gate/codex-review-gate.sh")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    ': "${BASE_SHA:?BASE_SHA is required}"\n',
    'BASE_SHA="${BASE_SHA:-}"\nREVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-${BASE_SHA}}"\n: "${REVIEW_CONTEXT:?BASE_SHA or CODEX_REVIEW_CONTEXT is required}"\n',
    "context setup",
)
text = replace_once(
    text,
    'MODE="${CODEX_REVIEW_MODE:-wait}"\n',
    'MODE="${CODEX_REVIEW_MODE:-wait}"\nCHECK_NAME="${CODEX_REVIEW_CHECK_NAME:-}"\n',
    "status input",
)
text = replace_once(
    text,
    'MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${BASE_SHA} -->"\n',
    'MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${REVIEW_CONTEXT} -->"\n',
    "context marker",
)
text = replace_once(
    text,
    'COMMENT_CREATED_AT=""\n',
    'COMMENT_CREATED_AT=""\nSTATUS_STARTED="false"\nSTATUS_COMPLETED="false"\n',
    "status state",
)
text = replace_once(
    text,
    'and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and (.base.sha // "") == $base)',
    'and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and ($base == "" or (.base.sha // "") == $base))',
    "optional base provenance",
)
api_marker = '''api_list() {
  local endpoint="$1"
  gh api --paginate \\
    -H "Accept: application/vnd.github+json" \\
    "$endpoint" \\
    --jq '.[]' | jq -s '.'
}

'''
status_helpers = '''publish_status() {
  local state="$1"
  [[ -n "$CHECK_NAME" ]] || return 0
  gh api --method POST \\
    -H "Accept: application/vnd.github+json" \\
    "repos/${REPO}/statuses/${HEAD_SHA}" \\
    -f state="$state" \\
    -f context="$CHECK_NAME" \\
    -f description="Codex review gate: ${state}" >/dev/null
}

start_status() {
  [[ -n "$CHECK_NAME" ]] || return 0
  publish_status pending
  STATUS_STARTED="true"
}

complete_status() {
  local state="$1"
  [[ "$STATUS_STARTED" == "true" ]] || return 0
  publish_status "$state"
  STATUS_COMPLETED="true"
}

on_exit() {
  local status=$?
  if [[ "$status" -ne 0 && "$STATUS_STARTED" == "true" && "$STATUS_COMPLETED" != "true" ]]; then
    complete_status failure || true
  fi
}
trap on_exit EXIT

'''
text = replace_once(text, api_marker, api_marker + status_helpers, "status helpers")
text = replace_once(
    text,
    '''  wait)
    ;;
  *)
''',
    '''  wait)
    start_status
    ;;
  request-and-wait)
    start_status
    if has_clear_codex_evidence; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA} for this review context."
      complete_status success
      exit 0
    fi
    request_review
    ;;
  *)
''',
    "mode integration",
)
text = text.replace("    exit 0\n", "    complete_status success\n    exit 0\n")
text = text.replace("  exit 0\n", "  complete_status success\n  exit 0\n")
path.write_text(text, encoding="utf-8")

tests = Path("tests/test_codex_review_gate.py")
test_text = tests.read_text(encoding="utf-8")
addition = '''\n\ndef test_reusable_gate_preserves_context_and_pr_head_status_surface() -> None:\n    action = Path("actions/codex-review-gate/action.yml").read_text(encoding="utf-8")\n    script = GATE.read_text(encoding="utf-8")\n\n    assert "review-context:" in action\n    assert "CODEX_REVIEW_CONTEXT: ${{ inputs.review-context }}" in action\n    assert "check-name:" in action\n    assert "statuses:write" in action\n    assert "CODEX_REVIEW_CHECK_NAME: ${{ inputs.check-name }}" in action\n    assert "request-and-wait" in action\n    assert 'REVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-${BASE_SHA}}"' in script\n    assert '"repos/${REPO}/statuses/${HEAD_SHA}"' in script\n    assert "publish_status pending" in script\n    assert "complete_status success" in script\n\n\ndef test_codex_review_gate_shell_syntax() -> None:\n    import subprocess\n\n    subprocess.run(["bash", "-n", str(GATE)], check=True)\n'''
if "test_reusable_gate_preserves_context_and_pr_head_status_surface" not in test_text:
    test_text += addition
tests.write_text(test_text, encoding="utf-8")
