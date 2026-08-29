#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

MODE="${CODEX_REVIEW_MODE:-wait}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
SHORT_SHA="${HEAD_SHA:0:10}"
MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA} -->"
COMMENT_ID=""
OWNER="${REPO%%/*}"
NAME="${REPO#*/}"

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
    response="$(gh api "${args[@]}")"
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
    has_next="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage // false' <<<"$response")"
    [[ "$has_next" == "true" ]] || return 1
    cursor="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty' <<<"$response")"
    [[ -n "$cursor" ]] || return 1
  done
}

find_bot_trigger_comment() {
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
}

find_bootstrap_trigger_comment() {
  local comments
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
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
    fi
    return 0
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
