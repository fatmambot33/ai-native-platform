"""Bind AI review evidence to both pull-request head and base revisions."""

from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace one exact fragment or fail loudly."""
    if old not in text:
        raise SystemExit(f"missing replacement target: {label}")
    return text.replace(old, new, 1)


# Composite action contract.
path = Path("actions/codex-review-gate/action.yml")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    "  head-sha:\n    description: Current pull request HEAD SHA.\n    required: true\n",
    "  head-sha:\n    description: Current pull request HEAD SHA.\n    required: true\n"
    "  base-sha:\n    description: Current pull request base SHA.\n    required: true\n",
    "base-sha action input",
)
text = replace_once(
    text,
    "        HEAD_SHA: ${{ inputs.head-sha }}\n",
    "        HEAD_SHA: ${{ inputs.head-sha }}\n        BASE_SHA: ${{ inputs.base-sha }}\n",
    "base-sha action environment",
)
path.write_text(text, encoding="utf-8")

# Canonical workflow.
path = Path(".github/workflows/codex-review.yml")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "types: [opened, synchronize, reopened, ready_for_review]",
    "types: [opened, synchronize, reopened, ready_for_review, edited]",
)
text = text.replace(
    "          head-sha: ${{ github.event.pull_request.head.sha }}\n          mode:",
    "          head-sha: ${{ github.event.pull_request.head.sha }}\n"
    "          base-sha: ${{ github.event.pull_request.base.sha }}\n"
    "          mode:",
)
path.write_text(text, encoding="utf-8")

# Gate implementation.
path = Path("actions/codex-review-gate/codex-review-gate.sh")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    ': "${HEAD_SHA:?HEAD_SHA is required}"\n',
    ': "${HEAD_SHA:?HEAD_SHA is required}"\n: "${BASE_SHA:?BASE_SHA is required}"\n',
    "required base SHA",
)
text = replace_once(
    text,
    'MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA} -->"\n',
    'MARKER="<!-- ai-native-codex-review-gate:${HEAD_SHA}:${BASE_SHA} -->"\n',
    "head/base marker",
)
text = replace_once(
    text,
    'COMMENT_ID=""\n',
    'COMMENT_ID=""\nCOMMENT_CREATED_AT=""\n',
    "comment timestamp state",
)
old_review = '''has_matching_review() {
  local reviews
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \\
    --arg head "$HEAD_SHA" \\
    "any(.[]; (${is_codex_login}) and ((.state // \\\"\\\") != \\\"DISMISSED\\\") and ((.commit_id // \\\"\\\") == \\$head))" \\
    <<<"$reviews" >/dev/null
}
'''
new_review = '''has_matching_review() {
  local reviews
  find_trigger_comment
  [[ -n "$COMMENT_ID" && -n "$COMMENT_CREATED_AT" ]] || return 1
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \\
    --arg head "$HEAD_SHA" \\
    --arg since "$COMMENT_CREATED_AT" \\
    "any(.[]; (${is_codex_login}) and ((.state // \\\"\\\") != \\\"DISMISSED\\\") and ((.commit_id // \\\"\\\") == \\$head) and ((.submitted_at // \\\"\\\") >= \\$since))" \\
    <<<"$reviews" >/dev/null
}
'''
text = replace_once(text, old_review, new_review, "review freshness")
text = replace_once(
    text,
    '    --arg head "$HEAD_SHA" \\\n    --arg created_at "$comment_created_at" \\\n',
    '    --arg head "$HEAD_SHA" \\\n    --arg base "$BASE_SHA" \\\n    --arg created_at "$comment_created_at" \\\n',
    "trusted run base argument",
)
text = replace_once(
    text,
    '     and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head)\' \\\n',
    '     and any(.pull_requests[]?; .number == $pr and (.head.sha // "") == $head and (.base.sha // "") == $base)\' \\\n',
    "trusted run base binding",
)
text = replace_once(
    text,
    '      COMMENT_ID="$id"\n      return 0\n',
    '      COMMENT_ID="$id"\n      COMMENT_CREATED_AT="$created_at"\n      return 0\n',
    "bot request timestamp",
)
old_bootstrap = '''find_bootstrap_trigger_comment() {
  local comments
  COMMENT_ID=""
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  COMMENT_ID="$(
    jq -r \\
      --arg marker "$MARKER" \\
      '[
        .[]
        | select(
            (.author_association // "") == "OWNER"
            or (.author_association // "") == "MEMBER"
            or (.author_association // "") == "COLLABORATOR"
          )
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\\\r?\\\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | .id // empty' \\
      <<<"$comments"
  )"
}
'''
new_bootstrap = '''find_bootstrap_trigger_comment() {
  local comments row
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  comments="$(api_list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100")"
  row="$(
    jq -r \\
      --arg marker "$MARKER" \\
      '[
        .[]
        | select(
            (.author_association // "") == "OWNER"
            or (.author_association // "") == "MEMBER"
            or (.author_association // "") == "COLLABORATOR"
          )
        | select((.created_at // "") == (.updated_at // ""))
        | select((.body // "") | test("^@codex review(\\\\r?\\\\n|$)"))
        | select((.body // "") | contains($marker))
      ] | last | if . == null then "" else [.id, .created_at] | @tsv end' \\
      <<<"$comments"
  )"
  if [[ -n "$row" ]]; then
    IFS=$'\\t' read -r COMMENT_ID COMMENT_CREATED_AT <<<"$row"
  fi
}
'''
text = replace_once(text, old_bootstrap, new_bootstrap, "bootstrap timestamp")
text = replace_once(
    text,
    '''find_trigger_comment() {
  COMMENT_ID=""
  find_bot_trigger_comment
''',
    '''find_trigger_comment() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  find_bot_trigger_comment
''',
    "trigger timestamp reset",
)
path.write_text(text, encoding="utf-8")

# Structural validator.
path = Path("ai_native.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    'required = {"opened", "synchronize", "reopened", "ready_for_review"}',
    'required = {"opened", "synchronize", "reopened", "ready_for_review", "edited"}',
    "edited PR event requirement",
)
text = replace_once(
    text,
    '        "head-sha": "${{ github.event.pull_request.head.sha }}",\n        "mode": mode,\n',
    '        "head-sha": "${{ github.event.pull_request.head.sha }}",\n'
    '        "base-sha": "${{ github.event.pull_request.base.sha }}",\n'
    '        "mode": mode,\n',
    "base-sha structural input",
)
text = text.replace(
    "must run on opened, synchronize, reopened, and ready_for_review",
    "must run on opened, synchronize, reopened, ready_for_review, and edited",
)
path.write_text(text, encoding="utf-8")

# Validator fixtures.
for filename in (
    "tests/test_ai_review_governance_hardening.py",
    "tests/test_validation.py",
):
    path = Path(filename)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "          head-sha: ${{ github.event.pull_request.head.sha }}\n          mode:",
        "          head-sha: ${{ github.event.pull_request.head.sha }}\n"
        "          base-sha: ${{ github.event.pull_request.base.sha }}\n"
        "          mode:",
    )
    text = text.replace(
        "          head-sha: ${{{{ github.event.pull_request.head.sha }}}}\n          mode:",
        "          head-sha: ${{{{ github.event.pull_request.head.sha }}}}\n"
        "          base-sha: ${{{{ github.event.pull_request.base.sha }}}}\n"
        "          mode:",
    )
    path.write_text(text, encoding="utf-8")

path = Path("tests/test_ai_review_governance_hardening.py")
text = path.read_text(encoding="utf-8")
if "test_review_gate_requires_base_sha_input" not in text:
    text += '''


def test_review_gate_requires_base_sha_input(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          base-sha: ${{ github.event.pull_request.base.sha }}\\n", "", 1
    )
    _write_repository(tmp_path, workflow)
    assert any("canonical gate step" in item.message for item in _findings(tmp_path))


def test_review_gate_requires_edited_activity_when_types_are_restricted(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "  pull_request:\\n",
        "  pull_request:\\n    types: [opened, synchronize, reopened, ready_for_review]\\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("ready_for_review, and edited" in item.message for item in _findings(tmp_path))
'''
path.write_text(text, encoding="utf-8")

# Gate implementation regressions.
path = Path("tests/test_codex_review_gate.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    assert '(.head.sha // "") == $head' in trusted
    assert "ai-native-codex-review-run" in bot
''',
    '''    assert '(.head.sha // "") == $head' in trusted
    assert '(.base.sha // "") == $base' in trusted
    assert "ai-native-codex-review-run" in bot
''',
    "base provenance regression",
)
if "test_matching_review_must_follow_current_head_base_request" not in text:
    text += '''


def test_matching_review_must_follow_current_head_base_request() -> None:
    script = GATE.read_text(encoding="utf-8")
    review = _function_body(script, "has_matching_review")

    assert "find_trigger_comment" in review
    assert "COMMENT_CREATED_AT" in review
    assert ".submitted_at" in review
    assert ">= $since" in review
    assert "${HEAD_SHA}:${BASE_SHA}" in script
'''
path.write_text(text, encoding="utf-8")

# Documentation.
path = Path("docs/AI_REVIEW_GOVERNANCE.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "exact pull request number and HEAD SHA",
    "exact pull request number, HEAD SHA, and base SHA",
)
text = text.replace(
    "full current-HEAD marker",
    "full current head/base marker",
)
path.write_text(text, encoding="utf-8")

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "server-verified GitHub Actions request-run provenance.",
    "server-verified GitHub Actions request-run provenance scoped to both head and base revisions.",
)
path.write_text(text, encoding="utf-8")

path = Path("RELEASE_NOTES.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "exact PR and HEAD;",
    "exact PR, HEAD, and base revision;",
)
path.write_text(text, encoding="utf-8")
