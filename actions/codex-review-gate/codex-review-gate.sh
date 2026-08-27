#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${REPO:?REPO is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

HEAD_REPO="${HEAD_REPO:-$REPO}"
TIMEOUT_SECONDS="${CODEX_REVIEW_TIMEOUT_SECONDS:-1800}"
POLL_SECONDS="${CODEX_REVIEW_POLL_SECONDS:-60}"
REQUEST_ONLY="${CODEX_REVIEW_REQUEST_ONLY:-false}"
SHORT_SHA="${HEAD_SHA:0:10}"
MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA} -->"
COMMENT_ID=""

is_codex_login='(.user.login // "") | startswith("chatgpt-codex-connector")'

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
    --arg short "$SHORT_SHA" \
    "any(.[]; (${is_codex_login}) and ((.commit_id // \"\") == \$head or ((.body // \"\") | contains(\$short))))" \
    <<<"$reviews" >/dev/null
}

find_trigger_comment() {
  local comments
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
    jq -r \
      --arg marker "$MARKER" \
      --arg short "$SHORT_SHA" \
      '[.[] | select(((.body // "") | contains($marker)) or (((.body // "") | contains("@codex review")) and ((.body // "") | contains($short))))] | last | .id // empty' \
      <<<"$comments"
  )"
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

echo "Checking Codex evidence for current HEAD ${SHORT_SHA}."

if has_matching_review; then
  echo "Codex already reviewed current HEAD ${SHORT_SHA}."
  exit 0
fi

find_trigger_comment
if [[ -z "$COMMENT_ID" && "$HEAD_REPO" == "$REPO" ]]; then
  body="$(printf '@codex review\n\nAutomated AI Native Platform merge gate for `%s`.\n%s\n' "$SHORT_SHA" "$MARKER")"
  if response="$(
    gh api --method POST \
      "repos/${REPO}/issues/${PR_NUMBER}/comments" \
      -f body="$body" 2>/dev/null
  )"; then
    COMMENT_ID="$(jq -r '.id' <<<"$response")"
    echo "Requested Codex review for current HEAD ${SHORT_SHA}."
  else
    echo "::notice::This pull-request token cannot post the Codex request. A maintainer can comment '@codex review ${SHORT_SHA}' and the gate will bind Codex's response to that HEAD."
  fi
elif [[ -z "$COMMENT_ID" ]]; then
  echo "External PR detected. A maintainer can comment '@codex review ${SHORT_SHA}' to create HEAD-specific review evidence."
else
  echo "Codex review request for current HEAD ${SHORT_SHA} already exists."
fi

if [[ "$REQUEST_ONLY" == "true" || "$REQUEST_ONLY" == "1" ]]; then
  echo "Codex review request phase complete for ${SHORT_SHA}."
  exit 0
fi

deadline=$((SECONDS + TIMEOUT_SECONDS))
while (( SECONDS < deadline )); do
  if has_matching_review; then
    echo "Codex review matches current HEAD ${SHORT_SHA}."
    exit 0
  fi
  if has_trigger_clean_reaction; then
    echo "Codex reported no findings for current HEAD ${SHORT_SHA}."
    exit 0
  fi
  sleep "$POLL_SECONDS"
done

echo "::error::Codex has not completed a review of current HEAD ${SHORT_SHA}. Comment '@codex review ${SHORT_SHA}' on the PR if an automatic request could not be posted, then re-run this check after Codex responds."
exit 1
