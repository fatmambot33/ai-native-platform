from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing expected text in {path}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "ai_native.py",
    'expected_group = "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}"',
    'expected_group = (\n        "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}-"\n        "${{ github.event.pull_request.head.sha }}"\n    )',
)
replace(
    "ai_native.py",
    '    if _gate_optional_input(request, "review-context") != _gate_optional_input(\n        wait, "review-context"\n    ):\n        failures.append("request and wait jobs must use the same review-context")\n',
    '    request_context = _gate_optional_input(request, "review-context")\n    wait_context = _gate_optional_input(wait, "review-context")\n    if request_context != wait_context:\n        failures.append("request and wait jobs must use the same review-context")\n    elif request_context not in (None, "") and (\n        not isinstance(request_context, str)\n        or "${{" in request_context\n        or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,128}", request_context)\n    ):\n        failures.append(\n            "review-context must be absent or a non-expression literal using safe marker characters"\n        )\n',
)
replace(
    "validator/validate_standard.py",
    '        "docs/AI_REVIEW_GOVERNANCE.md",\n        "docs/RELEASE.md",',
    '        "docs/AI_REVIEW_GOVERNANCE.md",\n        "docs/SECURITY_EVIDENCE.md",\n        "docs/DISTRIBUTION.md",\n        "docs/RELEASE.md",',
)
replace(
    "actions/codex-review-gate/preflight.sh",
    '  if is_current_base_native_review_submission; then\n    if has_native_matching_review ""; then\n      :\n    else\n      review_status=$?\n      [[ "$review_status" -eq 1 ]] && return 1\n      echo "::error::Unable to prove the submitted Codex review remains live and non-dismissed."\n      return 2\n    fi\n',
    '  if is_current_base_native_review_submission; then\n    local event_review_id reviews\n    event_review_id="$(jq -r \'.review.id // empty\' "$GITHUB_EVENT_PATH")"\n    if [[ -z "$event_review_id" ]]; then\n      echo "::error::Submitted-review event is missing its review ID."\n      return 2\n    fi\n    if ! reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"; then\n      echo "::error::Unable to revalidate the submitted Codex review object."\n      return 2\n    fi\n    if jq -e --argjson review_id "$event_review_id" --arg head "$HEAD_SHA" \\\n      "any(.[]; (.id == \\$review_id) and (${is_codex_login}) and ((.state // \\\"\\\") != \\\"DISMISSED\\\") and ((.commit_id // \\\"\\\") == \\$head))" \\\n      <<<"$reviews" >/dev/null; then\n      :\n    else\n      review_status=$?\n      [[ "$review_status" -eq 1 ]] && return 1\n      echo "::error::Unable to prove the submitted Codex review remains live and non-dismissed."\n      return 2\n    fi\n',
)

path = Path("tests/test_pr35_final_governance.py")
text = path.read_text(encoding="utf-8")
text = text.replace('    assert \'has_native_matching_review ""\' in body\n', '    assert ".review.id // empty" in body\n    assert ".id == $review_id" in body\n')
addition = '''\n\ndef test_remaining_governance_findings_are_locked() -> None:\n    import ai_native\n\n    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")\n    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")\n    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")\n    source = inspect.getsource(ai_native._single_ai_review_workflow_findings)\n    assert "${{ github.event.pull_request.head.sha }}" in workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0]\n    assert "/docs/SECURITY_EVIDENCE.md @fatmambot33" in codeowners\n    assert "/docs/DISTRIBUTION.md @fatmambot33" in codeowners\n    assert '\"docs/SECURITY_EVIDENCE.md\",' in validator\n    assert '\"docs/DISTRIBUTION.md\",' in validator\n    assert '"${{" in request_context' in source\n    assert "[A-Za-z0-9._:/-]{1,128}" in source\n'''
if "test_remaining_governance_findings_are_locked" not in text:
    text += addition
path.write_text(text, encoding="utf-8")

# Touch after the publisher workflow exists so the path-filtered run starts.
