#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
: "${BASE_SHA:?BASE_SHA is required}"
: "${GITHUB_RUN_ID:?GITHUB_RUN_ID is required}"
: "${GITHUB_WORKFLOW_REF:?GITHUB_WORKFLOW_REF is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
SHORT_SHA="${HEAD_SHA:0:10}"
MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${BASE_SHA} -->"
RUN_MARKER="<!-- ai-native-codex-review-run:${GITHUB_RUN_ID} -->"
COMMENT_ID=""
COMMENT_CREATED_AT=""
OWNER="${REPO%%/*}"
NAME="${REPO#*/}"
WORKFLOW_PATH="${GITHUB_WORKFLOW_REF#${REPO}/}"
WORKFLOW_PATH="${WORKFLOW_PATH%@*}"

is_codex_login='((.user.login // "") == "chatgpt-codex-connector" or (.user.login // "") == "chatgpt-codex-connector[bot]")'

api_list() {
  local endpoint="$1"
  gh api --paginate \
    -H "Accept: application/vnd.github+json" \
    "$endpoint" \
    --jq '.[]' | jq -s '.'
}

has_matching_review() {
  local reviews
  find_trigger_comment
  [[ -n "$COMMENT_ID" && -n "$COMMENT_CREATED_AT" ]] || return 1
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \
    --arg head "$HEAD_SHA" \
    --arg since "$COMMENT_CREATED_AT" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head) and ((.submitted_at // \"\") >= \$since))" \
    <<<"$reviews" >/dev/null
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
     and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and (.base.sha // "") == $base)' \
    <<<"$run" >/dev/null
}

find_bot_trigger_comment() {
  local comments row id created_at run_id status
  COMMENT_ID=""
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
  if [[ -z "$COMMENT_ID" ]]; then
    find_bootstrap_trigger_comment
  fi
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

has_clear_codex_evidence() {
  if has_matching_review || has_trigger_clean_reaction; then
    if has_unresolved_codex_threads; then
      echo "Codex evidence exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
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

request_review() {
  find_bot_trigger_comment
  if [[ -n "$COMMENT_ID" ]]; then
    echo "Codex review request for current HEAD ${SHORT_SHA} already exists."
    return 0
  fi
  local body response
  body="$(printf '@codex review\n\nAutomated AI Native Platform merge gate for `%s`.\n%s\n%s\n' "$SHORT_SHA" "$MARKER" "$RUN_MARKER")"
  response="$(
    gh api --method POST \
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \
      -f body="$body"
  )"
  COMMENT_ID="$(jq -r '.id' <<<"$response")"
  echo "Requested Codex review for current HEAD ${SHORT_SHA}."
}

case "$MODE" in
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