"""One-shot recovery for PR #35 after the Codex worker could not push."""

from __future__ import annotations

import subprocess
from pathlib import Path

OLD_REF = "7bcc9fc17e6b4859870ca5c3c1aa599bba437dd5"


def run(*args: str) -> str:
    result = subprocess.run(args, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def replace_shell_function(source: str, name: str, body: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[:start] + body.rstrip() + "\n" + source[end:]


def insert_after_shell_function(source: str, name: str, addition: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[:end] + "\n" + addition.strip() + "\n\n" + source[end:]


def replace_python_function(source: str, name: str, body: str) -> str:
    start = source.index(f"def {name}(")
    next_def = source.find("\ndef ", start + 1)
    if next_def == -1:
        raise RuntimeError(f"Unable to find end of {name}")
    return source[:start] + body.rstrip() + "\n\n" + source[next_def + 1 :]


def require_replace(source: str, old: str, new: str, *, count: int = 1) -> str:
    if source.count(old) < count:
        raise RuntimeError(f"Expected replacement not found: {old[:100]!r}")
    return source.replace(old, new, count)


def patch_gate() -> None:
    path = Path("actions/codex-review-gate/codex-review-gate.sh")
    text = path.read_text(encoding="utf-8")

    text = replace_shell_function(
        text,
        "has_matching_review",
        r'''has_matching_review() {
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
}''',
    )

    text = replace_shell_function(
        text,
        "has_dismissed_matching_review",
        r'''has_dismissed_matching_review() {
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
}''',
    )

    text = replace_shell_function(
        text,
        "has_trigger_clean_reaction",
        r'''has_trigger_clean_reaction() {
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
}''',
    )

    text = replace_shell_function(
        text,
        "has_native_matching_review",
        r'''has_native_matching_review() {
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
}''',
    )

    text = replace_shell_function(
        text,
        "has_any_native_matching_review",
        r'''has_any_native_matching_review() {
  has_native_matching_review ""
}''',
    )

    text = replace_shell_function(
        text,
        "has_native_clean_reaction",
        r'''has_native_clean_reaction() {
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
}''',
    )

    helpers = r'''revision_runs() {
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
}'''
    text = insert_after_shell_function(text, "current_run_created_at", helpers)

    text = replace_shell_function(
        text,
        "has_any_native_clear_codex_evidence",
        r'''has_any_native_clear_codex_evidence() {
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
}''',
    )

    text = replace_shell_function(
        text,
        "has_native_clear_codex_evidence",
        r'''has_native_clear_codex_evidence() {
  local since="$1"
  : "$since"
  has_any_native_clear_codex_evidence
}''',
    )

    text = replace_shell_function(
        text,
        "has_clear_codex_evidence",
        r'''has_clear_codex_evidence() {
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
}''',
    )

    text = require_replace(
        text,
        '''request_review() {\n  if has_any_native_clear_codex_evidence; then\n    echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}; no fallback request needed."\n    return 0\n  fi\n''',
        '''request_review() {\n  local native_status\n  if has_any_native_clear_codex_evidence; then\n    echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}; no fallback request needed."\n    return 0\n  else\n    native_status=$?\n  fi\n  [[ "$native_status" -eq 1 ]] || return 2\n''',
    )

    text = require_replace(
        text,
        '''if has_any_native_clear_codex_evidence; then\n  echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}."\n  complete_status success\n  exit 0\nfi\n''',
        '''if has_any_native_clear_codex_evidence; then\n  echo "Reusing completed native Codex review for current HEAD ${SHORT_SHA}."\n  complete_status success\n  exit 0\nelse\n  native_status=$?\n  if [[ "$native_status" -eq 2 ]]; then\n    exit 2\n  fi\nfi\n''',
    )

    path.write_text(text, encoding="utf-8")
    subprocess.run(["bash", "-n", str(path)], check=True)


def patch_governance(core_sha: str) -> None:
    path = Path("ai_native.py")
    text = path.read_text(encoding="utf-8").replace(OLD_REF, core_sha)

    text = replace_python_function(
        text,
        "_workflow_events_value",
        '''def _workflow_events_value(workflow: Mapping[Any, Any]) -> Any:\n    """Return the parsed GitHub workflow event declaration."""\n    if "on" in workflow and True in workflow:\n        return None\n    events = workflow.get("on")\n    if events is None and True in workflow:\n        events = workflow.get(True)\n    return events''',
    )
    text = replace_python_function(
        text,
        "_event_runs_on_review_dismissal",
        '''def _event_runs_on_review_dismissal(workflow: Mapping[Any, Any]) -> bool:\n    """Return whether submitted and dismissed reviews both re-run governance."""\n    events = _workflow_events_value(workflow)\n    if not isinstance(events, Mapping) or "pull_request_review" not in events:\n        return False\n    config = events["pull_request_review"]\n    if not isinstance(config, Mapping):\n        return False\n    types = config.get("types")\n    if not isinstance(types, Sequence) or isinstance(types, (str, bytes)):\n        return False\n    return {"submitted", "dismissed"} <= {str(item) for item in types}''',
    )
    marker = "def _job_permissions(job: Mapping[str, Any]) -> Mapping[str, Any]:\n"
    helper = '''def _event_runs_on_review_thread_changes(workflow: Mapping[Any, Any]) -> bool:\n    """Return whether review-thread resolution changes re-run governance."""\n    events = _workflow_events_value(workflow)\n    if not isinstance(events, Mapping) or "pull_request_review_thread" not in events:\n        return False\n    config = events["pull_request_review_thread"]\n    if not isinstance(config, Mapping):\n        return False\n    types = config.get("types")\n    if not isinstance(types, Sequence) or isinstance(types, (str, bytes)):\n        return False\n    return {"resolved", "unresolved"} <= {str(item) for item in types}\n\n\n'''
    text = require_replace(text, marker, helper + marker)
    text = replace_python_function(
        text,
        "_uses_review_wait_events",
        '''def _uses_review_wait_events(job: Mapping[str, Any]) -> bool:\n    """Return whether the wait job runs on PR, review, and thread updates."""\n    condition = _normalize_condition(job.get("if"))\n    event_guard = (\n        "(github.event_name == 'pull_request' || github.event_name == 'pull_request_review' "\n        "|| github.event_name == 'pull_request_review_thread')"\n    )\n    draft_guard = f"{event_guard} && github.event.pull_request.draft == false"\n    reverse_guard = f"github.event.pull_request.draft == false && {event_guard}"\n    return condition in {event_guard, draft_guard, reverse_guard}''',
    )
    text = replace_python_function(
        text,
        "_codeowners_has_workflow_namespace_rule",
        '''def _codeowners_has_workflow_namespace_rule(root: Path) -> bool:\n    """Return whether the workflow namespace retains effective CODEOWNERS coverage."""\n    codeowners = root / ".github" / "CODEOWNERS"\n    if _path_has_symlink_component(root, Path(".github/CODEOWNERS")) or not codeowners.is_file():\n        return False\n    accepted = {\n        "/.github/workflows/**",\n        ".github/workflows/**",\n        "/.github/workflows/",\n        ".github/workflows/",\n    }\n    namespace_rule = False\n    for raw_line in codeowners.read_text(encoding="utf-8").splitlines():\n        line = raw_line.strip()\n        if not line or line.startswith("#"):\n            continue\n        parts = line.split()\n        if parts and parts[0] in accepted and parts[1:]:\n            if all(_valid_codeowner(owner) for owner in parts[1:]):\n                namespace_rule = True\n    if not namespace_rule:\n        return False\n    return _codeowners_covers_path(\n        root, Path(".github/workflows/__ai_native_unmatched_probe__.yml")\n    )''',
    )

    text = require_replace(
        text,
        "    failures: list[str] = []\n    if _has_forbidden_github_cli_env(workflow.get(\"env\")):\n",
        "    failures: list[str] = []\n    if \"on\" in workflow and True in workflow:\n        failures.append(\"workflow must not contain both YAML representations of the on event key\")\n    if _has_forbidden_github_cli_env(workflow.get(\"env\")):\n",
    )
    text = text.replace(
        'failures.append("pull_request_review must run on dismissed review events")',
        'failures.append("pull_request_review must explicitly run on submitted and dismissed review events")',
        1,
    )
    review_check = '''    if "pull_request_review" not in events or not _event_runs_on_review_dismissal(workflow):\n        failures.append("pull_request_review must explicitly run on submitted and dismissed review events")\n'''
    text = require_replace(
        text,
        review_check,
        review_check
        + '''    if "pull_request_review_thread" not in events or not _event_runs_on_review_thread_changes(workflow):\n        failures.append("pull_request_review_thread must explicitly run on resolved and unresolved events")\n''',
    )
    path.write_text(text, encoding="utf-8")

    workflow = Path(".github/workflows/codex-review.yml")
    value = workflow.read_text(encoding="utf-8").replace(OLD_REF, core_sha)
    value = require_replace(
        value,
        "  pull_request_review:\n    types: [submitted, dismissed]\n",
        "  pull_request_review:\n    types: [submitted, dismissed]\n  pull_request_review_thread:\n    types: [resolved, unresolved]\n",
    )
    value = value.replace(
        "(github.event_name == 'pull_request' || github.event_name == 'pull_request_review')",
        "(github.event_name == 'pull_request' || github.event_name == 'pull_request_review' || github.event_name == 'pull_request_review_thread')",
    )
    workflow.write_text(value, encoding="utf-8")

    codeowners = Path(".github/CODEOWNERS")
    value = codeowners.read_text(encoding="utf-8")
    for line in ("/CHANGELOG.md @fatmambot33\n", "/RELEASE_NOTES.md @fatmambot33\n"):
        if line not in value:
            value += line
    codeowners.write_text(value, encoding="utf-8")

    validator = Path("validator/validate_standard.py")
    value = validator.read_text(encoding="utf-8")
    value = require_replace(
        value,
        '        "AGENTS.md",\n        "pyproject.toml",\n',
        '        "AGENTS.md",\n        "CHANGELOG.md",\n        "RELEASE_NOTES.md",\n        "pyproject.toml",\n',
    )
    validator.write_text(value, encoding="utf-8")

    for candidate in Path("tests").glob("test_*.py"):
        value = candidate.read_text(encoding="utf-8")
        if OLD_REF in value:
            value = value.replace(OLD_REF, core_sha)
        candidate.write_text(value, encoding="utf-8")

    fixtures = [
        Path("tests/test_ai_review_governance_hardening.py"),
        Path("tests/test_ai_review_governance_remaining.py"),
        Path("tests/test_validation.py"),
    ]
    old_condition = "(github.event_name == 'pull_request' || github.event_name == 'pull_request_review')"
    new_condition = "(github.event_name == 'pull_request' || github.event_name == 'pull_request_review' || github.event_name == 'pull_request_review_thread')"
    for candidate in fixtures:
        value = candidate.read_text(encoding="utf-8")
        value = value.replace("types: [dismissed]", "types: [submitted, dismissed]")
        review_trigger = "  pull_request_review:\n    types: [submitted, dismissed]\n"
        if "pull_request_review_thread:" not in value:
            value = value.replace(
                review_trigger,
                review_trigger + "  pull_request_review_thread:\n    types: [resolved, unresolved]\n",
                1,
            )
        value = value.replace(old_condition, new_condition)
        value = value.replace(
            'assert any("pull_request_review must run on dismissed" in item.message for item in findings)',
            'assert any("submitted and dismissed" in item.message for item in findings)',
        )
        candidate.write_text(value, encoding="utf-8")

    hardening = Path("tests/test_ai_review_governance_hardening.py")
    value = hardening.read_text(encoding="utf-8")
    value += '''\n\ndef test_review_gate_requires_submitted_review_activity(tmp_path: Path) -> None:\n    workflow = WORKFLOW.replace("types: [submitted, dismissed]", "types: [dismissed]", 1)\n    _write_repository(tmp_path, workflow)\n    assert any("submitted and dismissed" in item.message for item in _findings(tmp_path))\n\n\ndef test_review_gate_requires_review_thread_revalidation(tmp_path: Path) -> None:\n    workflow = WORKFLOW.replace(\n        "  pull_request_review_thread:\\n    types: [resolved, unresolved]\\n", "", 1\n    )\n    _write_repository(tmp_path, workflow)\n    assert any("resolved and unresolved" in item.message for item in _findings(tmp_path))\n\n\ndef test_review_gate_rejects_ambiguous_on_keys(tmp_path: Path) -> None:\n    workflow = WORKFLOW.replace("on:\\n", '\"on\":\\n', 1) + "\\non:\\n  push:\\n"\n    _write_repository(tmp_path, workflow)\n    assert any("both YAML representations" in item.message for item in _findings(tmp_path))\n\n\ndef test_review_gate_namespace_rule_must_remain_effective(tmp_path: Path) -> None:\n    _write_repository(tmp_path)\n    codeowners = tmp_path / ".github" / "CODEOWNERS"\n    codeowners.write_text(\n        "/.github/workflows/** @repository-owner\\n"\n        "/.github/**\\n"\n        "/.github/workflows/codex-review.yml @repository-owner\\n"\n        "/.github/CODEOWNERS @repository-owner\\n",\n        encoding="utf-8",\n    )\n    assert any("namespace rule" in item.message for item in _findings(tmp_path))\n'''
    hardening.write_text(value, encoding="utf-8")

    gate_tests = Path("tests/test_codex_review_gate.py")
    value = gate_tests.read_text(encoding="utf-8")
    value += '''\n\ndef test_native_evidence_is_reusable_for_exact_revision() -> None:\n    script = GATE.read_text(encoding="utf-8")\n    reusable = _function_body(script, "has_any_native_clear_codex_evidence")\n    assert "revision_activation_created_at" in reusable\n    assert "has_trusted_native_review_run" in reusable\n    assert "has_native_matching_review" in reusable\n\n\ndef test_native_clean_reaction_remains_revision_bound_evidence() -> None:\n    script = GATE.read_text(encoding="utf-8")\n    reusable = _function_body(script, "has_any_native_clear_codex_evidence")\n    assert "has_single_base_for_head" in reusable\n    assert "has_native_clean_reaction" in reusable\n\n\ndef test_dismissal_query_errors_fail_closed() -> None:\n    script = GATE.read_text(encoding="utf-8")\n    reaction = _function_body(script, "has_trigger_clean_reaction")\n    assert "dismissal_status" in reaction\n    assert "Unable to prove marker-backed review evidence is not dismissed" in reaction\n'''
    gate_tests.write_text(value, encoding="utf-8")

    final_tests = Path("tests/test_pr35_final_governance.py")
    value = final_tests.read_text(encoding="utf-8").replace(OLD_REF, core_sha)
    value += '''\n\ndef test_release_records_are_codeowner_governed() -> None:\n    codeowners = Path(".github/CODEOWNERS").read_text(encoding="utf-8")\n    validator = Path("validator/validate_standard.py").read_text(encoding="utf-8")\n    assert "/CHANGELOG.md @fatmambot33" in codeowners\n    assert "/RELEASE_NOTES.md @fatmambot33" in codeowners\n    assert '\"CHANGELOG.md\",' in validator\n    assert '\"RELEASE_NOTES.md\",' in validator\n'''
    final_tests.write_text(value, encoding="utf-8")


def main() -> None:
    patch_gate()
    run("git", "add", "actions/codex-review-gate/codex-review-gate.sh")
    run("git", "commit", "-m", "fix: preserve base-bound Codex evidence")
    core_sha = run("git", "rev-parse", "HEAD")

    patch_governance(core_sha)
    Path(".github/workflows/recover-pr35.yml").unlink()
    Path(".github/scripts/recover_pr35.py").unlink()
    run("git", "add", "-A")
    run("git", "commit", "-m", "fix: close current Codex governance findings")
    print(core_sha)


if __name__ == "__main__":
    main()
