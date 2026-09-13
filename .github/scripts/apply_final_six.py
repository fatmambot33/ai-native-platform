"""Apply the six final Codex governance remediations in CI."""

from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_gate() -> None:
    path = Path("actions/codex-review-gate/codex-review-gate.sh")
    replace_once(
        path,
        '''find_trigger_comment() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  find_bot_trigger_comment
  if [[ -z "$COMMENT_ID" ]]; then
    find_bootstrap_trigger_comment
  fi
}
''',
        '''find_trigger_comment() {
  COMMENT_ID=""
  COMMENT_CREATED_AT=""
  find_bot_trigger_comment
}
''',
        "remove collaborator bootstrap fallback",
    )
    replace_once(
        path,
        '''  [[ -n "$COMMENT_ID" ]] || return 1
  local reactions
''',
        '''  [[ -n "$COMMENT_ID" ]] || return 1
  if has_dismissed_matching_review; then
    return 1
  fi
  local reactions
''',
        "dismissal invalidates reaction",
    )
    replace_once(
        path,
        '''has_native_clean_reaction() {
''',
        '''has_any_native_matching_review() {
  local reviews
  reviews="$(api_list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100")"
  jq -e \\
    --arg head "$HEAD_SHA" \\
    "any(.[]; (${is_codex_login}) and ((.state // \\\"\\\") != \\\"DISMISSED\\\") and ((.commit_id // \\\"\\\") == \\$head))" \\
    <<<"$reviews" >/dev/null
}

has_any_native_clear_codex_evidence() {
  if ! has_any_native_matching_review; then
    return 1
  fi
  if has_unresolved_codex_threads; then
    echo "Native Codex review exists for current HEAD ${SHORT_SHA}, but unresolved Codex review threads remain."
    return 1
  fi
  local thread_status=$?
  if [[ "$thread_status" -eq 1 ]]; then
    return 0
  fi
  echo "::error::Unable to prove that all Codex review threads are resolved for current HEAD ${SHORT_SHA}."
  return 1
}

has_native_clean_reaction() {
''',
        "late native review helpers",
    )
    replace_once(
        path,
        '''request_review() {
  find_bot_trigger_comment
''',
        '''request_review() {
  if has_any_native_clear_codex_evidence; then
    echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}; no fallback request needed."
    return 0
  fi
  find_bot_trigger_comment
''',
        "reuse late native review before request",
    )
    replace_once(
        path,
        '''if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  complete_status success
  exit 0
fi

if is_native_review_event; then
''',
        '''if has_clear_codex_evidence; then
  echo "Codex review is current and all Codex review threads are resolved for ${SHORT_SHA}."
  complete_status success
  exit 0
fi

if has_any_native_clear_codex_evidence; then
  echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}."
  complete_status success
  exit 0
fi

if is_native_review_event; then
''',
        "reuse late native review in wait path",
    )


def patch_conformance() -> None:
    path = Path("ai_native.py")
    replace_once(
        path,
        '''    return uses[len(prefix) :]


def _permission_declaration_is_forbidden''',
        '''    return uses[len(prefix) :]


def _gate_optional_input(job: Mapping[str, Any], key: str) -> Any:
    """Return one optional canonical gate input, normalizing omission to empty."""
    steps = job.get("steps", [])
    if (
        not isinstance(steps, Sequence)
        or isinstance(steps, (str, bytes))
        or len(steps) != 1
        or not isinstance(steps[0], Mapping)
    ):
        return ""
    inputs = steps[0].get("with", {})
    if not isinstance(inputs, Mapping):
        return ""
    return inputs.get(key, "")


def _permission_declaration_is_forbidden''',
        "optional gate input helper",
    )
    replace_once(
        path,
        '''    if request_ref is not None and wait_ref is not None and request_ref != wait_ref:
        failures.append("request and wait jobs must pin the same gate revision")

    if _has_forbidden_write_permissions(workflow):
''',
        '''    if request_ref is not None and wait_ref is not None and request_ref != wait_ref:
        failures.append("request and wait jobs must pin the same gate revision")
    if _gate_optional_input(request, "review-context") != _gate_optional_input(
        wait, "review-context"
    ):
        failures.append("request and wait jobs must use the same review-context")

    if _has_forbidden_write_permissions(workflow):
''',
        "matching review context validation",
    )


def patch_standard() -> None:
    path = Path("standard/AI_NATIVE_PLATFORM.yaml")
    replace_once(
        path,
        '''    request_while_ci_runs: false
    reference_action: actions/codex-review-gate
''',
        '''    request_while_ci_runs: false
    reference_action: actions/codex-review-gate
    release_gates:
      - branch_up_to_date
''',
        "conditional AI review release gate",
    )
    replace_once(
        path,
        '''  - changelog_current
  - migration_notes_for_breaking_changes
  - branch_up_to_date
''',
        '''  - changelog_current
  - migration_notes_for_breaking_changes
''',
        "remove unconditional branch freshness gate",
    )


def patch_ownership() -> None:
    codeowners = Path(".github/CODEOWNERS")
    text = codeowners.read_text(encoding="utf-8")
    if "/AGENTS.md @fatmambot33\n" not in text:
        text += "/AGENTS.md @fatmambot33\n"
        codeowners.write_text(text, encoding="utf-8")

    validator = Path("validator/validate_standard.py")
    replace_once(
        validator,
        '''        "docs/AI_REVIEW_GOVERNANCE.md",
        "pyproject.toml",
''',
        '''        "docs/AI_REVIEW_GOVERNANCE.md",
        "AGENTS.md",
        "pyproject.toml",
''',
        "root agent policy governed path",
    )


def patch_docs() -> None:
    path = Path("docs/AI_REVIEW_GOVERNANCE.md")
    replace_once(
        path,
        '''The one-time bootstrap path accepts an unedited request from an `OWNER`, `MEMBER`, or `COLLABORATOR` when the new trusted `pull_request_target` workflow is not yet present on the default branch. The first line must be the exact `@codex review` command and the comment must contain the full current head/base marker. Bootstrap evidence is accepted only from a submitted Codex review whose GitHub `commit_id` matches the exact current HEAD and whose submission follows that request; reaction-only bootstrap evidence is never trusted. This is an explicitly privileged bootstrap exception rather than automated run provenance; request mode never creates or relies on it.
''',
        '''Collaborator-authored bootstrap markers are not trusted as review evidence because GitHub review objects do not carry a server-verifiable base SHA. Until the trusted `pull_request_target` request workflow is present on the default branch, an exact-HEAD native Codex review may be used only through the native-review path; marker-backed evidence requires bot-authored requests tied to server-verifiable workflow-run provenance.
''',
        "remove bootstrap documentation",
    )


def add_tests() -> None:
    remaining = Path("tests/test_ai_review_governance_remaining.py")
    text = remaining.read_text(encoding="utf-8")
    if "test_review_gate_requires_matching_review_contexts" not in text:
        text += r'''


def test_review_gate_requires_matching_review_contexts(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          mode: request\n",
        "          mode: request\n          review-context: request-only\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("same review-context" in item.message for item in _findings(tmp_path))


def test_review_gate_accepts_matching_review_contexts(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          request-label: codex:review\n",
        "          request-label: codex:review\n          review-context: shared\n",
        2,
    )
    _write_repository(tmp_path, workflow)
    assert not _findings(tmp_path)
'''
        remaining.write_text(text, encoding="utf-8")

    gate_tests = Path("tests/test_codex_review_gate.py")
    text = gate_tests.read_text(encoding="utf-8")
    if "test_gate_removes_unverifiable_collaborator_bootstrap" not in text:
        text += r'''


def test_gate_removes_unverifiable_collaborator_bootstrap() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("find_trigger_comment() {", 1)[1].split("}\n", 1)[0]
    assert "find_bot_trigger_comment" in block
    assert "find_bootstrap_trigger_comment" not in block


def test_dismissed_review_invalidates_clean_request_reaction() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("has_trigger_clean_reaction() {", 1)[1].split("\n}\n", 1)[0]
    assert "has_dismissed_matching_review" in block
    assert block.index("has_dismissed_matching_review") < block.index("reactions=")


def test_gate_reuses_late_native_review_before_fallback_request() -> None:
    source = Path("actions/codex-review-gate/codex-review-gate.sh").read_text(encoding="utf-8")
    block = source.split("request_review() {", 1)[1].split("\n}\n", 1)[0]
    assert "has_any_native_clear_codex_evidence" in block
    assert block.index("has_any_native_clear_codex_evidence") < block.index("gh api --method POST")
'''
        gate_tests.write_text(text, encoding="utf-8")

    standard_tests = Path("tests/test_standard.py")
    text = standard_tests.read_text(encoding="utf-8")
    if "test_branch_freshness_is_scoped_to_ai_review" not in text:
        text += r'''


def test_branch_freshness_is_scoped_to_ai_review() -> None:
    standard = yaml.safe_load(
        (ROOT / "standard/AI_NATIVE_PLATFORM.yaml").read_text(encoding="utf-8")
    )
    assert "branch_up_to_date" not in standard["release_gates"]
    assert "branch_up_to_date" in standard["governance"]["ai_review"]["release_gates"]


def test_root_agent_policy_is_codeowner_protected() -> None:
    codeowners = (ROOT / ".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = (ROOT / "validator/validate_standard.py").read_text(encoding="utf-8")
    assert "/AGENTS.md @fatmambot33" in codeowners
    assert '"AGENTS.md",' in validator
'''
        standard_tests.write_text(text, encoding="utf-8")


def main() -> None:
    patch_gate()
    patch_conformance()
    patch_standard()
    patch_ownership()
    patch_docs()
    add_tests()


if __name__ == "__main__":
    main()
