#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
: "${BASE_SHA:?BASE_SHA is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
CUSTOM_CONTEXT="${CODEX_REVIEW_CONTEXT:-}"

if ! [[ "$TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ && "$POLL_SECONDS" =~ ^[1-9][0-9]*$ ]]; then
  echo "::error::Codex review timeout and poll intervals must be positive ASCII decimal integers."
  exit 1
fi

if (( POLL_SECONDS > TIMEOUT_SECONDS )); then
  POLL_SECONDS="$TIMEOUT_SECONDS"
fi
export CODEX_REVIEW_POLL_SECONDS="$POLL_SECONDS"

# Always bind review evidence to both the exact base revision and any caller context.
export CODEX_REVIEW_CONTEXT="${BASE_SHA}:${CUSTOM_CONTEXT}"

verify_codeowners() {
  local response
  if ! response="$(gh api -H "Accept: application/vnd.github+json" "repos/${REPO}/codeowners/errors?ref=${HEAD_SHA}")"; then
    echo "::error::Unable to verify CODEOWNERS with GitHub for current HEAD ${HEAD_SHA:0:10}."
    return 2
  fi
  if ! jq -e '(.errors | type == "array") and ((.errors | length) == 0)' <<<"$response" >/dev/null; then
    echo "::error::GitHub reports invalid or ineffective CODEOWNERS entries for current HEAD ${HEAD_SHA:0:10}."
    jq -r '.errors[]? | "::error::CODEOWNERS line \(.line // "?"): \(.message // .kind // "invalid owner")"' <<<"$response"
    return 1
  fi
}

verify_codeowners

if [[ "$MODE" == "request-and-wait" ]]; then
  : "${GITHUB_EVENT_PATH:?GITHUB_EVENT_PATH is required for request-and-wait}"
  event_name="${GITHUB_EVENT_NAME:-}"
  event_action="$(jq -r '.action // empty' "$GITHUB_EVENT_PATH")"
  event_label="$(jq -r '.label.name // empty' "$GITHUB_EVENT_PATH")"
  if [[ "$event_name" != "pull_request_target" || "$event_action" != "labeled" || "$event_label" != "$REQUEST_LABEL" ]]; then
    echo "::error::request-and-wait may consume review quota only on an explicit ${REQUEST_LABEL} label event."
    exit 1
  fi
fi

exec bash "$GITHUB_ACTION_PATH/codex-review-gate.sh"
