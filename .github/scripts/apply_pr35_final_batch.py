"""Apply the final focused PR #35 governance remediation batch."""

from pathlib import Path
import re


def replace_once(path: str, old: str, new: str) -> None:
    """Replace one expected block, failing if neither old nor new is present."""
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old in text:
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
    elif new not in text:
        raise SystemExit(f"missing expected replacement in {path}: {old[:80]!r}")


def main() -> None:
    """Apply the five verified Codex findings and focused regressions."""
    expr = "$" + "{{ "
    event_name = expr + "github.event_name }}"
    pr_number = expr + "github.event.pull_request.number }}"
    head_sha = expr + "github.event.pull_request.head.sha }}"
    github_token = expr + "github.token }}"
    secret_token = expr + "secrets.PRODUCTION_TOKEN }}"

    # 1. Revalidate the exact review object carried by submitted-review events.
    preflight = Path("actions/codex-review-gate/preflight.sh")
    text = preflight.read_text(encoding="utf-8")
    helper = r'''
event_review_is_live() {
  local review_id review status
  review_id="$(jq -r '.review.id // empty' "$GITHUB_EVENT_PATH")"
  [[ -n "$review_id" ]] || return 1
  if ! review="$(gh api -H "Accept: application/vnd.github+json" "repos/${REPO}/pulls/${PR_NUMBER}/reviews/${review_id}")"; then
    echo "::error::Unable to revalidate the submitted Codex review object."
    return 2
  fi
  if jq -e \
    --arg head "$HEAD_SHA" \
    '(((.user.login // "") == "chatgpt-codex-connector") or ((.user.login // "") == "chatgpt-codex-connector[bot]")) and ((.state // "") != "DISMISSED") and ((.commit_id // "") == $head)' \
    <<<"$review" >/dev/null; then
    return 0
  else
    status=$?
  fi
  [[ "$status" -eq 1 ]] && return 1
  return 2
}
'''
    anchor = "\n# Reusable native evidence must come from a live, non-dismissed exact-HEAD review\n"
    if "event_review_is_live() {" not in text:
        if anchor not in text:
            raise SystemExit("preflight helper anchor missing")
        text = text.replace(anchor, helper + anchor, 1)
    old = '''  if is_current_base_native_review_submission; then
    if has_native_matching_review ""; then
      :
    else
      review_status=$?
      [[ "$review_status" -eq 1 ]] && return 1
      echo "::error::Unable to prove the submitted Codex review remains live and non-dismissed."
      return 2
    fi
'''
    new = '''  if is_current_base_native_review_submission; then
    if event_review_is_live; then
      :
    else
      review_status=$?
      [[ "$review_status" -eq 1 ]] && return 1
      echo "::error::Unable to prove the submitted Codex review remains live and non-dismissed."
      return 2
    fi
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit("submitted-review live-state block missing")
    preflight.write_text(text, encoding="utf-8")

    # 2. Scope concurrency validation to the exact PR HEAD.
    old_group = f"codex-review-{event_name}-{pr_number}"
    new_group = f"{old_group}-{head_sha}"
    replace_once(
        "ai_native.py",
        f'expected_group = "{old_group}"',
        f'expected_group = "{new_group}"',
    )

    # Patch the workflow only in the checkout for deterministic validation. The
    # publisher intentionally does not stage workflow files; the connector will.
    workflow = Path(".github/workflows/codex-review.yml")
    workflow_text = workflow.read_text(encoding="utf-8")
    workflow_text = workflow_text.replace(f"group: {old_group}", f"group: {new_group}")
    workflow.write_text(workflow_text, encoding="utf-8")

    # 3. Constrain review-context to a safe, non-expression literal.
    ai_native = Path("ai_native.py")
    text = ai_native.read_text(encoding="utf-8")
    helper = '''

def _safe_review_context(value: Any) -> bool:
    """Return whether review context is absent or a safe non-expression literal."""
    if value in (None, ""):
        return True
    if not isinstance(value, str) or len(value) > 128:
        return False
    return re.fullmatch(r"[A-Za-z0-9._:/-]+", value) is not None
'''
    anchor = "\n\ndef _permission_declaration_is_forbidden(value: Any) -> bool:\n"
    if "def _safe_review_context(" not in text:
        if anchor not in text:
            raise SystemExit("review-context helper anchor missing")
        text = text.replace(anchor, helper + anchor, 1)
    old = '''    if _gate_optional_input(request, "review-context") != _gate_optional_input(
        wait, "review-context"
    ):
        failures.append("request and wait jobs must use the same review-context")
'''
    new = '''    request_context = _gate_optional_input(request, "review-context")
    wait_context = _gate_optional_input(wait, "review-context")
    if request_context != wait_context:
        failures.append("request and wait jobs must use the same review-context")
    elif not _safe_review_context(request_context):
        failures.append(
            "review-context must be absent or a safe non-expression literal "
            "containing only letters, digits, dot, underscore, colon, slash, or hyphen"
        )
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit("review-context validation block missing")
    ai_native.write_text(text, encoding="utf-8")

    # 4. Protect the remaining security/distribution governance documents.
    codeowners = Path(".github/CODEOWNERS")
    text = codeowners.read_text(encoding="utf-8")
    marker = "/docs/AI_REVIEW_GOVERNANCE.md @fatmambot33\n"
    for line in (
        "/docs/SECURITY_EVIDENCE.md @fatmambot33\n",
        "/docs/DISTRIBUTION.md @fatmambot33\n",
    ):
        if line not in text:
            if marker not in text:
                raise SystemExit("CODEOWNERS governance anchor missing")
            text = text.replace(marker, marker + line, 1)
    codeowners.write_text(text, encoding="utf-8")

    validator = Path("validator/validate_standard.py")
    text = validator.read_text(encoding="utf-8")
    marker = '        "docs/AI_REVIEW_GOVERNANCE.md",\n'
    additions = '        "docs/SECURITY_EVIDENCE.md",\n        "docs/DISTRIBUTION.md",\n'
    if '"docs/SECURITY_EVIDENCE.md",' not in text:
        if marker not in text:
            raise SystemExit("canonical governed-path anchor missing")
        text = text.replace(marker, marker + additions, 1)
    validator.write_text(text, encoding="utf-8")

    # 5. Synchronize adoption guidance with reaction exclusion.
    docs = Path("docs/AI_REVIEW_GOVERNANCE.md")
    text = docs.read_text(encoding="utf-8")
    old = '''job reuses that native review and treats the current GitHub workflow run's
server timestamp as the activation boundary. It accepts only exact-current-HEAD
Codex review evidence created after that boundary (or a clean Codex PR reaction
created after it), and it never emits a second `@codex review` request for the
same checkpoint.
'''
    new = '''job reuses native evidence only when GitHub exposes a live, non-dismissed
exact-current-HEAD Codex review object with server-verifiable workflow-run
provenance and no unresolved Codex threads. PR-level reactions are not
revision-addressed and therefore are not reusable native success evidence. A
reaction-only result must complete through the marker-backed fallback request
path instead.
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit("governance reaction guidance block missing")
    docs.write_text(text, encoding="utf-8")

    # Focused regression coverage.
    tests = Path("tests/test_pr35_final_governance.py")
    text = tests.read_text(encoding="utf-8")
    addition = f'''


def test_submitted_review_rechecks_event_review_id_live_state() -> None:
    preflight = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert "event_review_is_live()" in preflight
    assert "pulls/${{PR_NUMBER}}/reviews/${{review_id}}" in preflight
    body = preflight.split("has_any_native_clear_codex_evidence() {{", 1)[1].split("\\n}}\\n", 1)[0]
    assert "if event_review_is_live; then" in body


def test_review_wait_concurrency_is_scoped_to_head() -> None:
    import ai_native

    source = inspect.getsource(ai_native._single_ai_review_workflow_findings)
    workflow = Path(".github/workflows/codex-review.yml").read_text(encoding="utf-8")
    expected = "{new_group}"
    assert expected in source
    assert f"group: {{expected}}" in workflow


def test_review_context_rejects_expressions_and_accepts_safe_literals() -> None:
    import ai_native

    assert ai_native._safe_review_context("")
    assert ai_native._safe_review_context("release/v0.4:checkpoint-1")
    assert not ai_native._safe_review_context("{github_token}")
    assert not ai_native._safe_review_context("{secret_token}")


def test_security_evidence_and_distribution_docs_are_codeowner_governed() -> None:
    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")
    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")
    for relative in ("docs/SECURITY_EVIDENCE.md", "docs/DISTRIBUTION.md"):
        assert f"/{{relative}} @fatmambot33" in codeowners
        assert f'"{{relative}}",' in validator


def test_governance_docs_exclude_pr_reactions_as_native_success() -> None:
    docs = Path("docs/AI_REVIEW_GOVERNANCE.md").read_text(encoding="utf-8")
    assert "PR-level reactions are not" in docs
    assert "reaction-only result must complete through the marker-backed fallback" in docs
'''
    if "test_submitted_review_rechecks_event_review_id_live_state" not in text:
        text += addition
    tests.write_text(text, encoding="utf-8")

    # When the connector has pinned the canonical workflow to the published
    # action-source commit, synchronize the trusted ref and regression constant.
    workflow_text = workflow.read_text(encoding="utf-8")
    refs = re.findall(
        r"ai-native-platform/actions/codex-review-gate@([0-9a-f]{40})",
        workflow_text,
    )
    if refs and len(set(refs)) == 1:
        ref = refs[0]
        text = ai_native.read_text(encoding="utf-8")
        text = re.sub(
            r'TRUSTED_AI_REVIEW_GATE_REFS = frozenset\(\n    \{\n        "[0-9a-f]{40}",\n    \}\n\)',
            'TRUSTED_AI_REVIEW_GATE_REFS = frozenset(\n    {\n        "' + ref + '",\n    }\n)',
            text,
            count=1,
        )
        ai_native.write_text(text, encoding="utf-8")
        text = tests.read_text(encoding="utf-8")
        text = re.sub(
            r'REMEDIATED_GATE_REF = "[0-9a-f]{40}"',
            f'REMEDIATED_GATE_REF = "{ref}"',
            text,
            count=1,
        )
        tests.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
