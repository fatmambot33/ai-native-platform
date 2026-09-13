#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
REVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-}"
CHECK_NAME="${CODEX_REVIEW_CHECK_NAME:-}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
SHORT_SHA="${HEAD_SHA:0:10}"
if [[ -n "$REVIEW_CONTEXT" ]]; then
  MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${REVIEW_CONTEXT} -->"
else
  MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA} -->"
fi
COMMENT_ID=""
COMMENT_CREATED_AT=""
STATUS_STARTED="false"
STATUS_COMPLETED="false"

is_codex_login='((.user.login // "") == "chatgpt-codex-connector" or (.user.login // "") == "chatgpt-codex-connector[bot]")'

api_list() {
  local endpoint="$1"
  gh api --paginate \
    -H "Accept: application/vnd.github+json" \
    "$endpoint" \
    --jq '.[]' | jq -s '.'
}

publish_status() {
  local state="$1"
  [[ -n "$CHECK_NAME" ]] || return 0
  gh api --method POST \
    -H "Accept: application/vnd.github+json" \
    "repos/${REPO}/statuses/${HEAD_SHA}" \
    -f state="$state" \
    -f context="$CHECK_NAME" \
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

find_trigger_comment() {
  local comments
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
    jq -r \
      --arg marker "$MARKER" \
      '[
        .[]
        | select((.user.login // "") == "github-actions[bot]")
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | .id // empty' \
      <<<"$comments"
  )"
  COMMENT_CREATED_AT="$(
    jq -r \
      --arg marker "$MARKER" \
      '[
        .[]
        | select((.user.login // "") == "github-actions[bot]")
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | .created_at // empty' \
      <<<"$comments"
  )"
}

has_matching_review() {
  local reviews
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  if [[ -n "$REVIEW_CONTEXT" ]]; then
    [[ -n "$COMMENT_ID" ]] || find_trigger_comment
    [[ -n "$COMMENT_ID" && -n "$COMMENT_CREATED_AT" ]] || return 1
    jq -e \
      --arg head "$HEAD_SHA" \
      --arg requested_at "$COMMENT_CREATED_AT" \
      "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$requested_at))" \
      <<<"$reviews" >/dev/null
    return
  fi
  jq -e \
    --arg head "$HEAD_SHA" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head))" \
    <<<"$reviews" >/dev/null
}

has_trigger_clean_reaction() {
  [[ -n "$COMMENT_ID" ]] || find_trigger_comment
  [[ -n "$COMMENT_ID" ]] || return 1
  local reactions
  reactions="$(api_list "repos/${REPO}/issues/comments/${COMMENT_ID}/reactions?per_page=100")"
  jq -e \
    "any(.[]; (${is_codex_login}) and .content == \"+1\")" \
    <<<"$reactions" >/dev/null
}

request_review() {
  find_trigger_comment
  if [[ -n "$COMMENT_ID" ]]; then
    echo "Codex review request for current HEAD ${SHORT_SHA} and review context already exists."
    return 0
  fi
  local body response
  body="$(printf '@codex review\n\nAutomated AI Native Platform merge gate for `%s`.\n%s\n' "$SHORT_SHA" "$MARKER")"
  response="$(
    gh api --method POST \
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \
      -f body="$body"
  )"
  COMMENT_ID="$(jq -r '.id' <<<"$response")"
  COMMENT_CREATED_AT="$(jq -r '.created_at // empty' <<<"$response")"
  echo "Requested Codex review for current HEAD ${SHORT_SHA}."
}

wait_for_review() {
  echo "Waiting for Codex evidence for current HEAD ${SHORT_SHA}."
  local deadline=$((SECONDS + TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if has_matching_review; then
      echo "Codex review matches current HEAD ${SHORT_SHA} and review context."
      return 0
    fi
    if has_trigger_clean_reaction; then
      echo "Codex reported no findings for current HEAD ${SHORT_SHA} and review context."
      return 0
    fi
    sleep "$POLL_SECONDS"
  done
  echo "::error::Codex has not completed a review of current HEAD ${SHORT_SHA} for this review context."
  return 1
}

case "$MODE" in
  request)
    if has_matching_review; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA} for this review context."
      exit 0
    fi
    request_review
    exit 0
    ;;
  wait)
    start_status
    if wait_for_review; then
      complete_status success
      exit 0
    fi
    exit 1
    ;;
  request-and-wait)
    start_status
    if has_matching_review; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA} for this review context."
      complete_status success
      exit 0
    fi
    request_review
    if wait_for_review; then
      complete_status success
      exit 0
    fi
    exit 1
    ;;
  *)
    echo "::error::Unknown Codex review gate mode: ${MODE}."
    exit 2
    ;;
esac
