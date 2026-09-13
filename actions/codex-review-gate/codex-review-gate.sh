#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
BASE_SHA="${BASE_SHA:-}"
REVIEW_CONTEXT="${CODEX_REVIEW_CONTEXT:-${BASE_SHA}}"
: "${REVIEW_CONTEXT:?BASE_SHA or CODEX_REVIEW_CONTEXT is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
: "${GITHUB_WORKFLOW_REF:?GITHUB_WORKFLOW_REF is required}"
: "${GITHUB_EVENT_NAME:?GITHUB_EVENT_NAME is required}"
: "${GITHUB_EVENT_PATH:?GITHUB_EVENT_PATH is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
CHECK_NAME="${CODEX_REVIEW_CHECK_NAME:-}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
REQUEST_LABEL="${CODEX_REVIEW_REQUEST_LABEL:-codex:review}"
SHORT_SHA="${HEAD_SHA:0:10}"
MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${REVIEW_CONTEXT} -->"
RUN_MARKER="<!-- ai-native-codex-review-run:${GITHUB_RUN_ID} -->"
COMMENT_ID=""
COMMENT_CREATED_AT=""
STATUS_STARTED="false"
STATUS_COMPLETED="false"
OWNER="${REPO%%/*}"
NAME="${REPO#*/}"
WORKFLOW_PATH="${GITHUB_WORKFLOW_REF#${REPO}/}"
WORKFLOW_PATH="${WORKFLOW_PATH%@*}"
EVENT_ACTION="$(jq -r '.action // empty' "$GITHUB_EVENT_PATH")"
EVENT_LABEL="$(jq -r '.label.name // empty' "$GITHUB_EVENT_PATH")"
EVENT_BASE_SHA="$(jq -r '.pull_request.base.sha // empty' "$GITHUB_EVENT_PATH")"
EVENT_REVIEW_COMMIT_SHA="$(jq -r '.review.commit_id // empty' "$GITHUB_EVENT_PATH")"
EVENT_REVIEW_AUTHOR="$(jq -r '.review.user.login // empty' "$GITHUB_EVENT_PATH")"

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

is_request_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request_target" \
    && "$EVENT_ACTION" == "labeled" \
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}

is_wait_label_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \
    && "$EVENT_ACTION" == "labeled" \
    && "$EVENT_LABEL" == "$REQUEST_LABEL" ]]
}

is_native_review_event() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request" \
    && ( "$EVENT_ACTION" == "opened" || "$EVENT_ACTION" == "ready_for_review" ) ]]
}

is_current_base_native_review_submission() {
  [[ "$GITHUB_EVENT_NAME" == "pull_request_review" \
    && "$EVENT_ACTION" == "submitted" \
    && "$EVENT_BASE_SHA" == "$BASE_SHA" \
    && "$EVENT_REVIEW_COMMIT_SHA" == "$HEAD_SHA" \
    && ( "$EVENT_REVIEW_AUTHOR" == "chatgpt-codex-connector" \
      || "$EVENT_REVIEW_AUTHOR" == "chatgpt-codex-connector[bot]" ) ]]
}

clear_request_label() {
  local encoded_label
  encoded_label="$(jq -rn --arg value "$REQUEST_LABEL" '$value | @uri')"
  if ! gh api --method DELETE \
    "repos/${REPO}/issues/${PR_NUMBER}/labels/${encoded_label}" >/dev/null 2>&1; then
    echo "::warning::Unable to clear one-shot Codex review label ${REQUEST_LABEL}."
  fi
  return 0
}

has_matching_review() {
  local reviews status
  if ! find_trigger_comment; then
    return 2
  fi
  [[ -n "$COMMENT_ID" && -n "$COMMENT_CREATED_AT" ]] || return 1
  if ! reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"; then
    echo "::error::Unable to query Codex reviews for marker-backed evidence."
    return 2
  fi
  if jq -e \
    --arg head "$HEAD_SHA" \
    --arg since "$COMMENT_CREATED_AT" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$since))" \
    <<<"$reviews" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  echo "::error::Unable to evaluate Codex review evidence."
  return 2
}

has_dismissed_matching_review() {
  local reviews status
  if ! find_trigger_comment; then
    return 2
  fi
  [[ -n "$COMMENT_ID" && -n "$COMMENT_CREATED_AT" ]] || return 1
  if ! reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"; then
    echo "::error::Unable to query dismissed Codex reviews."
    return 2
  fi
  if jq -e \
    --arg head "$HEAD_SHA" \
    --arg since "$COMMENT_CREATED_AT" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") == \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$since))" \
    <<<"$reviews" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  echo "::error::Unable to evaluate dismissed Codex review evidence."
  return 2
}

has_unresolved_codex_threads() {
  local query cursor response has_next
  query='query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
    repository(owner: $owner, name: $name) {
      pullRequest(number: $number) {
        reviewThreads(first: 100, after: $cursor) {
          nodes {
            isResolved
            comments(first: 1) {
              nodes { author { login } }
            }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
  }'
  cursor=""
  while true; do
    local -a args=(
      graphql
      -f "query=${query}"
      -F "owner=${OWNER}"
      -F "name=${NAME}"
      -F "number=${PR_NUMBER}"
    )
    if [[ -n "$cursor" ]]; then
      args+=(-f "cursor=${cursor}")
    fi
    if ! response="$(gh api "${args[@]}")"; then
      echo "::error::Unable to query Codex review-thread state from GitHub GraphQL."
      return 2
    fi
    if ! jq -e '
      ((.errors? // []) | length == 0)
      and (.data.repository.pullRequest.reviewThreads.nodes | type == "array")
      and (.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage | type == "boolean")
      and (
        (.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage == false)
        or (
          (.data.repository.pullRequest.reviewThreads.pageInfo.endCursor | type == "string")
          and (.data.repository.pullRequest.reviewThreads.pageInfo.endCursor | length > 0)
        )
      )
    ' <<<"$response" >/dev/null; then
      echo "::error::GitHub returned malformed or errored Codex review-thread data."
      return 2
    fi
    if jq -e '
      any(
        .data.repository.pullRequest.reviewThreads.nodes[]?;
        (.isResolved == false)
        and (
          (.comments.nodes[0].author.login // "") == "chatgpt-codex-connector"
          or (.comments.nodes[0].author.login // "") == "chatgpt-codex-connector[bot]"
        )
      )
    ' <<<"$response" >/dev/null; then
      return 0
    fi
    has_next="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<<"$response")"
    [[ "$has_next" == "true" ]] || return 1
    cursor="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor' <<<"$response")"
    if [[ -z "$cursor" || "$cursor" == "null" ]]; then
      echo "::error::GitHub review-thread pagination omitted a required cursor."
      return 2
    fi
  done
}

current_workflow_id() {
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

revision_runs() {
  local workflow_id runs
  if ! workflow_id="$(current_workflow_id)"; then
    return 2
  fi
  if ! runs="$(
    gh api --paginate \
      -H "Accept: application/vnd.github+json" \
      "repos/${REPO}/actions/workflows/${workflow_id}/runs?per_page=100" \
      --jq '.workflow_runs[]' | jq -s '.'
  )"; then
    echo "::error::Unable to query governance workflow runs for the current revision."
    return 2
  fi
  printf '%s\n' "$runs"
}

revision_activation_created_at() {
  local runs created_at
  if ! runs="$(revision_runs)"; then
    return 2
  fi
  created_at="$(jq -r \
    --arg workflow_path "$WORKFLOW_PATH" \
    --arg head "$HEAD_SHA" \
    --arg base "$BASE_SHA" \
    --argjson pr "$PR_NUMBER" \
    '[.[] | select(
      .path == $workflow_path
      and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and (.base.sha // "") == $base)
    ) | (.created_at // empty)] | min // ""' \
    <<<"$runs")"
  [[ -n "$created_at" ]] || return 1
  printf '%s\n' "$created_at"
}

has_trusted_native_review_run() {
  local runs status
  if ! runs="$(revision_runs)"; then
    return 2
  fi
  if jq -e \
    --arg workflow_path "$WORKFLOW_PATH" \
    --arg head "$HEAD_SHA" \
    --arg base "$BASE_SHA" \
    --argjson pr "$PR_NUMBER" \
    'any(.[];
      .path == $workflow_path
      and .event == "pull_request_review"
      and (
        (.actor.login // "") == "chatgpt-codex-connector"
        or (.actor.login // "") == "chatgpt-codex-connector[bot]"
      )
      and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and (.base.sha // "") == $base)
    )' \
    <<<"$runs" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  return 2
}

has_single_base_for_head() {
  local runs status
  if ! runs="$(revision_runs)"; then
    return 2
  fi
  if jq -e \
    --arg workflow_path "$WORKFLOW_PATH" \
    --arg head "$HEAD_SHA" \
    --arg base "$BASE_SHA" \
    --argjson pr "$PR_NUMBER" \
    '[.[] | select(
      .path == $workflow_path
      and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head)
    ) | [.pull_requests[]? | select(.number == $pr and (.head.sha // "") == $head) | (.base.sha // "")]]
    | flatten | unique == [$base]' \
    <<<"$runs" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  return 2
}


trusted_request_run() {
  local run_id="$1"
  local comment_created_at="$2"
  local workflow_id run
  if ! workflow_id="$(current_workflow_id)"; then
    return 2
  fi
  if ! run="$(gh api "repos/${REPO}/actions/runs/${run_id}")"; then
    echo "::error::Unable to load request workflow run ${run_id}."
    return 2
  fi
  jq -e \
    --arg workflow_id "$workflow_id" \
    --arg workflow_path "$WORKFLOW_PATH" \
    --arg head "$HEAD_SHA" \
    --arg base "$BASE_SHA" \
    --arg created_at "$comment_created_at" \
    --argjson pr "$PR_NUMBER" \
    '(.workflow_id | tostring) == $workflow_id
     and .event == "pull_request_target"
     and .path == $workflow_path
     and ((.created_at // "") <= $created_at)
     and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and ($base == "" or (.base.sha // "") == $base))' \
    <<<"$run" >/dev/null
}

find_bot_trigger_comment() {
  local comments row id created_at run_id status
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  if ! comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"; then
    echo "::error::Unable to query Codex review-request comments."
    return 2
  fi
  while IFS=$'\t' read -r id created_at run_id; do
    [[ -n "$id" ]] || continue
    if trusted_request_run "$run_id" "$created_at"; then
      COMMENT_ID="$id"
      COMMENT_CREATED_AT="$created_at"
      return 0
    fi
    status=$?
    if [[ "$status" -eq 2 ]]; then
      return 2
    fi
  done < <(
    jq -r \
      --arg marker "$MARKER" \
      '[
        .[]
        | select((.user.login // "") == "github-actions[bot]")
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
        | . as $comment
        | (try (($comment.body // "") | capture("<!-- ai-native-codex-review-run:(?<run_id>[0-9]+) -->")) catch null) as $run
        | select($run != null)
        | [$comment.id, $comment.created_at, $run.run_id]
      ] | reverse[] | @tsv' \
      <<<"$comments"
  )
  return 0
}

find_bootstrap_trigger_comment() {
  local comments row
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  row="$(
    jq -r \
      --arg marker "$MARKER" \
      '[
        .[]
        | select(
            (.author_association // "") == "OWNER"
            or (.author_association // "") == "MEMBER"
            or (.author_association // "") == "COLLABORATOR"
          )
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | if . == null then "" else [.id, .created_at] | @tsv end' \
      <<<"$comments"
  )"
  if [[ -n "$row" ]]; then
    IFS=$'\t' read -r COMMENT_ID COMMENT_CREATED_AT <<<"$row"
  fi
}

find_trigger_comment() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  find_bot_trigger_comment
}

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
      '[
        .[]
        | select(
            (.user.login // "") == "chatgpt-codex-connector"
            or (.user.login // "") == "chatgpt-codex-connector[bot]"
          )
        | select((.created_at // "") >= $since)
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

has_trigger_clean_reaction() {
  local dismissal_status reactions reaction_status
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  if ! find_bot_trigger_comment; then
    return 2
  fi
  [[ -n "$COMMENT_ID" ]] || return 1
  if has_dismissed_matching_review; then
    return 1
  else
    dismissal_status=$?
  fi
  if [[ "$dismissal_status" -ne 1 ]]; then
    echo "::error::Unable to prove marker-backed review evidence is not dismissed."
    return 2
  fi
  if ! reactions="$(api_list "repos/${REPO}/issues/comments/${COMMENT_ID}/reactions?per_page=100")"; then
    echo "::error::Unable to query Codex request-comment reactions."
    return 2
  fi
  if jq -e \
    "any(.[]; (${is_codex_login}) and .content == \"+1\")" \
    <<<"$reactions" >/dev/null; then
    return 0
  else
    reaction_status=$?
  fi
  [[ "$reaction_status" -eq 1 ]] && return 1
  return 2
}


has_native_matching_review() {
  local since="$1"
  local reviews status
  if ! reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"; then
    echo "::error::Unable to query native Codex reviews."
    return 2
  fi
  if jq -e \
    --arg head "$HEAD_SHA" \
    --arg since "$since" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$since))" \
    <<<"$reviews" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  return 2
}

has_any_native_matching_review() {
  has_native_matching_review ""
}

has_any_native_clear_codex_evidence() {
  local activation activation_status thread_status run_status review_status base_status reaction_status

  if is_current_base_native_review_submission; then
    if has_unresolved_codex_threads; then
      echo "Native Codex review exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
      return 1
    else
    local thread_status=$?
      if [[ "$thread_status" -eq 1 ]]; then
        return 0
      fi
      echo "::error::Unable to prove that all Codex review threads are resolved for current HEAD ${SHORT_SHA}."
      return 2
    fi
  fi

  if activation="$(revision_activation_created_at)"; then
    :
  else
    activation_status=$?
    [[ "$activation_status" -eq 1 ]] && return 1
    return 2
  fi

  if has_unresolved_codex_threads; then
    echo "Native Codex evidence exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
    return 1
  else
    thread_status=$?
  fi
  if [[ "$thread_status" -ne 1 ]]; then
    echo "::error::Unable to prove that all Codex review threads are resolved for current HEAD ${SHORT_SHA}."
    return 2
  fi

  if has_trusted_native_review_run; then
    if has_native_matching_review "$activation"; then
      return 0
    else
      review_status=$?
    fi
    [[ "$review_status" -eq 1 ]] || return 2
  else
    run_status=$?
    [[ "$run_status" -eq 1 ]] || return 2
  fi

  if has_single_base_for_head; then
    if has_native_clean_reaction "$activation"; then
      return 0
    else
      reaction_status=$?
    fi
    [[ "$reaction_status" -eq 1 ]] || return 2
  else
    base_status=$?
    [[ "$base_status" -eq 1 ]] || return 2
  fi
  return 1
}

has_native_clean_reaction() {
  local since="$1"
  local reactions status
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

has_native_clear_codex_evidence() {
  local since="$1"
  : "$since"
  has_any_native_clear_codex_evidence
}

has_clear_codex_evidence() {
  local review_status reaction_status thread_status
  if has_matching_review; then
    :
  else
    review_status=$?
    if [[ "$review_status" -eq 2 ]]; then
      return 2
    fi
    if has_trigger_clean_reaction; then
      :
    else
      reaction_status=$?
      [[ "$reaction_status" -eq 1 ]] && return 1
      return 2
    fi
  fi
  if has_unresolved_codex_threads; then
    echo "Codex evidence exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
    return 1
  else
    thread_status=$?
  fi
  if [[ "$thread_status" -eq 1 ]]; then
    return 0
  fi
  echo "::error::Unable to prove that all Codex review threads are resolved for current HEAD ${SHORT_SHA}."
  return 2
}

request_review() {
  local native_status
  if has_any_native_clear_codex_evidence; then
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
    elif codex_failure_after "$COMMENT_CREATED_AT" >/dev/null; then
      echo "Prior Codex request failed; this explicit ${REQUEST_LABEL} event authorizes one retry."
    else
      local failure_status=$?
      if [[ "$failure_status" -eq 1 ]]; then
        echo "A Codex review request for current HEAD ${SHORT_SHA} is still pending; preserving quota."
        return 0
      fi
      return 2
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

case "$MODE" in
  request)
    if ! is_request_label_event; then
      echo "Codex review request skipped. Apply ${REQUEST_LABEL} only when the PR is merge-ready."
      complete_status success
      exit 0
    fi
    trap clear_request_label EXIT
    if has_matching_review; then
      echo "Codex already reviewed current HEAD ${SHORT_SHA}."
      complete_status success
      exit 0
    fi
    request_review
    complete_status success
    exit 0
    ;;
  wait)
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
    request_started_at="${COMMENT_CREATED_AT:-}"
    if [[ -z "$request_started_at" ]]; then
      request_started_at="$(current_run_created_at)" || exit 2
    fi
    echo "Waiting for the requested Codex review of current HEAD ${SHORT_SHA}."
    deadline=$((SECONDS + TIMEOUT_SECONDS))
    while (( SECONDS < deadline )); do
      if has_clear_codex_evidence; then
        echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
        complete_status success
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
    echo "::error::Codex has not completed a clean review of current HEAD ${SHORT_SHA}."
    echo "::error::Re-run request-and-wait only after confirming the earlier request completed or failed."
    exit 1
    ;;
  *)
    echo "::error::Unknown Codex review gate mode: ${MODE}."
    exit 2
    ;;
esac

if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  complete_status success
  exit 0
fi

if has_any_native_clear_codex_evidence; then
  echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}."
  complete_status success
  exit 0
else
  native_status=$?
  if [[ "$native_status" -eq 2 ]]; then
    exit 2
  fi
fi

if is_native_review_event; then
  request_started_at="$(current_run_created_at)" || exit 2
  echo "Waiting for the native Codex review of current HEAD ${SHORT_SHA}; no duplicate request will be sent."
  deadline=$((SECONDS + TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    if has_native_clear_codex_evidence "$request_started_at"; then
      echo "Native Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
      complete_status success
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
  echo "::error::Current HEAD ${SHORT_SHA} has no clean Codex review."
  echo "::error::Run deterministic CI and batch fixes, then apply ${REQUEST_LABEL} once merge-ready."
  exit 1
fi

request_started_at="$(current_run_created_at)" || exit 2
echo "Waiting for one merge-ready Codex review of current HEAD ${SHORT_SHA}."
deadline=$((SECONDS + TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if has_clear_codex_evidence; then
    echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
    complete_status success
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

echo "::error::Codex has not completed a clean review of current HEAD ${SHORT_SHA}."
echo "::error::Re-apply ${REQUEST_LABEL} only after confirming the earlier request completed or failed."
exit 1
