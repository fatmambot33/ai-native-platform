#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"
: "${GITHUB_EVENT_PATH:?GITHUB_EVENT_PATH is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
SHORT_SHA="${HEAD_SHA:0:10}"
MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA} -->"
COMMENT_ID=""
OWNER="${REPO%%/*}"
NAME="${REPO#*/}"
HEAD_ACTIVE_SINCE="$(
  jq -er \
    --arg head "$HEAD_SHA" \
    'select((.pull_request.head.sha // "") == $head)
     | .pull_request.updated_at
     | select(type == "string" and length > 0)' \
    "$GITHUB_EVENT_PATH"
)" || {
  echo "::error::Unable to prove when current PR HEAD ${SHORT_SHA} became active from the GitHub event payload."
  exit 2
}

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
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \
    --arg head "$HEAD_SHA" \
    "any(.[]; (${is_codex_login}) and ((.state // \"\") != \"DISMISSED\") and ((.commit_id // \"\") == \$head))" \
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

find_bot_trigger_comment() {
  local comments
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
    jq -r \
      --arg marker "$MARKER" \
      --arg active_since "$HEAD_ACTIVE_SINCE" \
      '[
        .[]
        | select((.user.login // "") == "github-actions[bot]")
        | select((.created_at // "") == (.updated_at // ""))
        | select((.created_at // "") >= $active_since)
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | .id // empty' \
      <<<"$comments"
  )"
}

find_bootstrap_trigger_comment() {
  local comments
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
    jq -r \
      --arg marker "$MARKER" \
      --arg active_since "$HEAD_ACTIVE_SINCE" \
      '[
        .[]
        | select(
            (.author_association // "") == "OWNER"
            or (.author_association // "") == "MEMBER"
            or (.author_association // "") == "COLLABORATOR"
          )
        | select((.created_at // "") == (.updated_at // ""))
        | select((.created_at // "") >= $active_since)
        | select((.body // "") | test("^@codex review(\\r?\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | .id // empty' \
      <<<"$comments"
  )"
}

find_trigger_comment() {
  COMMENT_ID=""
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
  body="$(printf '@codex review\n\nAutomated AI Native Platform merge gate for `%s`.\n%s\n' "$SHORT_SHA" "$MARKER")"
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
