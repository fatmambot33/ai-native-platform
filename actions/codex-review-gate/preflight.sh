#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
: "${BASE_SHA:?BASE_SHA is required}"
: "${GITHUB_ACTION_PATH:?GITHUB_ACTION_PATH is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
CUSTOM_CONTEXT="${CODEX_REVIEW_CONTEXT:-}"
GATE_SCRIPT="$GITHUB_ACTION_PATH/codex-review-gate.sh"

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

verify_live_revision() {
  local pull live_head live_base
  if ! pull="$(gh api -H "Accept: application/vnd.github+json" "repos/${REPO}/pulls/${PR_NUMBER}")"; then
    echo "::error::Unable to revalidate the live pull-request revision before success."
    return 2
  fi
  live_head="$(jq -r '.head.sha // empty' <<<"$pull")"
  live_base="$(jq -r '.base.sha // empty' <<<"$pull")"
  if [[ "$live_head" != "$HEAD_SHA" || "$live_base" != "$BASE_SHA" ]]; then
    echo "::error::Pull-request revision changed while the Codex gate was running."
    echo "::error::Expected HEAD/base ${HEAD_SHA:0:10}/${BASE_SHA:0:10}, got ${live_head:0:10}/${live_base:0:10}."
    return 1
  fi
}

verify_codeowners

if [[ "$MODE" == "request-and-wait" ]]; then
  : "${GITHUB_EVENT_PATH:?GITHUB_EVENT_PATH is required for request-and-wait}"
  event_name="${GITHUB_EVENT_NAME:-}"
  event_action="$(jq -r '.action // empty' "$GITHUB_EVENT_PATH")"
  event_label="$(jq -r '.label.name // empty' "$GITHUB_EVENT_PATH")"
  event_draft="$(jq -r '.pull_request.draft // true' "$GITHUB_EVENT_PATH")"
  if [[ "$event_name" != "pull_request_target" || "$event_action" != "labeled" || "$event_label" != "$REQUEST_LABEL" || "$event_draft" != "false" ]]; then
    echo "::error::request-and-wait may consume review quota only on an explicit ${REQUEST_LABEL} label event for a non-draft PR."
    exit 1
  fi
fi

# Load the canonical gate definitions without executing its control flow. The
# overrides below tighten runtime invariants while keeping one implementation of
# the request/review/thread semantics.
# shellcheck disable=SC1090
source <(sed '/^case "$MODE" in/,$d' "$GATE_SCRIPT")

is_request_label_event() {
  local draft
  draft="$(jq -r '.pull_request.draft // true' "$GITHUB_EVENT_PATH")"
  [[ "$GITHUB_EVENT_NAME" == "pull_request_target" \
    && "$EVENT_ACTION" == "labeled" \
    && "$EVENT_LABEL" == "$REQUEST_LABEL" \
    && "$draft" == "false" ]]
}

revision_runs() {
  local workflow_id now modified cache_ttl tmp_cache
  cache_ttl="$POLL_SECONDS"
  if (( cache_ttl > 1 )); then
    cache_ttl=$((cache_ttl - 1))
  fi
  if [[ -s "$REVISION_RUNS_CACHE_FILE" ]]; then
    now="$(date +%s)"
    modified="$(stat -c %Y "$REVISION_RUNS_CACHE_FILE" 2>/dev/null || printf '0')"
    if (( now - modified < cache_ttl )); then
      cat "$REVISION_RUNS_CACHE_FILE"
      return 0
    fi
  fi
  if ! workflow_id="$(current_workflow_id)"; then
    return 2
  fi
  tmp_cache="${REVISION_RUNS_CACHE_FILE}.tmp.$$"
  rm -f "$tmp_cache"
  if ! gh api --paginate \
      -H "Accept: application/vnd.github+json" \
      "repos/${REPO}/actions/workflows/${workflow_id}/runs?head_sha=${HEAD_SHA}&per_page=100" \
      --jq '.workflow_runs[]' | jq -s '.' >"$tmp_cache"; then
    rm -f "$tmp_cache"
    echo "::error::Unable to query governance workflow runs for the current revision."
    return 2
  fi
  if ! jq -e 'type == "array"' "$tmp_cache" >/dev/null; then
    rm -f "$tmp_cache"
    echo "::error::GitHub returned malformed governance workflow-run data."
    return 2
  fi
  mv "$tmp_cache" "$REVISION_RUNS_CACHE_FILE"
  cat "$REVISION_RUNS_CACHE_FILE"
}

has_dismissed_native_review_since() {
  local since="$1"
  local reviews status
  if ! reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"; then
    echo "::error::Unable to query dismissed native Codex reviews."
    return 2
  fi
  if jq -e \
    --arg head "$HEAD_SHA" \
    --arg since "$since" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") == \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$since))" \
    <<<"$reviews" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  echo "::error::Unable to evaluate dismissed native Codex review evidence."
  return 2
}

has_native_clean_reaction() {
  local since="$1"
  local dismissal_status reactions status
  if has_dismissed_native_review_since "$since"; then
    return 1
  else
    dismissal_status=$?
  fi
  if [[ "$dismissal_status" -ne 1 ]]; then
    echo "::error::Unable to prove native reaction evidence is not dismissed."
    return 2
  fi
  if ! reactions="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/reactions?per_page=100")"; then
    echo "::error::Unable to query native Codex reactions."
    return 2
  fi
  if jq -e \
    --arg since "$since" \
    "any(.[]; (${is_codex_login}) and .content == \"+1\" and ((.created_at // \"\") >= \$since))" \
    <<<"$reactions" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  return 2
}

# Terminal bot comments are accepted only when they carry the exact revision
# marker. Uncorrelated delayed failures from an older HEAD/base are ignored and
# the current request remains pending until evidence arrives or the gate times out.
codex_failure_after() {
  local since="$1"
  local comments body
  if ! comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"; then
    echo "::error::Unable to inspect Codex review-request failures."
    return 2
  fi
  body="$(
    jq -r \
      --arg since "$since" \
      --arg marker "$MARKER" \
      '[
        .[]
        | select(
            (.user.login // "") == "chatgpt-codex-connector"
            or (.user.login // "") == "chatgpt-codex-connector[bot]"
          )
        | select((.created_at // "") >= $since)
        | select((.body // "") | contains($marker))
        | select(
            ((.body // "") | contains("reached your Codex usage limits for code reviews"))
            or ((.body // "") | startswith("Codex Review: Something went wrong"))
          )
        | .body
      ] | first // empty' \
      <<<"$comments"
  )"
  [[ -n "$body" ]] || return 1
  if [[ "$body" == *"usage limits for code reviews"* ]]; then
    echo "::error::Codex code-review quota is unavailable. No automatic retry will be attempted."
  else
    echo "::error::Codex reported a terminal review-request failure. No automatic retry will be attempted."
  fi
  return 0
}

request_review() {
  local native_status dismissal_status failure_status
  NATIVE_EVIDENCE_REUSED="false"
  if has_any_native_clear_codex_evidence; then
    NATIVE_EVIDENCE_REUSED="true"
    echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}; no fallback request needed."
    return 0
  else
    native_status=$?
  fi
  [[ "$native_status" -eq 1 ]] || return 2

  find_bot_trigger_comment
  if [[ -n "$COMMENT_ID" ]]; then
    if has_dismissed_matching_review; then
      echo "Matching Codex review was dismissed; this explicit ${REQUEST_LABEL} event authorizes one replacement review."
    else
      dismissal_status=$?
      if [[ "$dismissal_status" -ne 1 ]]; then
        echo "::error::Unable to prove whether the matching Codex review was dismissed."
        return 2
      fi
      if codex_failure_after "$COMMENT_CREATED_AT" >/dev/null; then
        echo "Prior Codex request failed; this explicit ${REQUEST_LABEL} event authorizes one retry."
      else
        failure_status=$?
        if [[ "$failure_status" -eq 1 ]]; then
          echo "A Codex review request for current HEAD ${SHORT_SHA} is still pending; preserving quota."
          return 0
        fi
        return 2
      fi
    fi
  fi

  local body response
  body="$(
    printf '@codex review\n\nQuota-aware merge-ready AI Native Platform gate for `%s`.\n%s\n%s\n' \
      "$SHORT_SHA" "$MARKER" "$RUN_MARKER"
  )"
  response="$(
    gh api --method POST \
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \
      -f body="$body"
  )"
  COMMENT_ID="$(jq -r '.id' <<<"$response")"
  COMMENT_CREATED_AT="$(jq -r '.created_at' <<<"$response")"
  echo "Requested one Codex review for merge-ready HEAD ${SHORT_SHA}."
}

complete_status() {
  local state="$1"
  if [[ "$state" == "success" ]]; then
    verify_live_revision
  fi
  [[ "$STATUS_STARTED" == "true" ]] || return 0
  publish_status "$state"
  STATUS_COMPLETED="true"
}

on_exit_with_request_label() {
  local status=$?
  clear_request_label || true
  if [[ "$status" -ne 0 && "$STATUS_STARTED" == "true" && "$STATUS_COMPLETED" != "true" ]]; then
    complete_status failure || true
  fi
  return "$status"
}

if [[ "$MODE" == "request-and-wait" ]]; then
  trap on_exit_with_request_label EXIT
fi

# Execute the canonical gate flow with the hardened runtime overrides above.
# shellcheck disable=SC1090
source <(sed -n '/^case "$MODE" in/,$p' "$GATE_SCRIPT")
