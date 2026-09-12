"""One-shot patcher for final Codex governance findings."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path.cwd()
OLD_REF = "db5cb7440dac086137afc93e32a69a6230556f57"
GROUP = "codex-review-${{ github.event_name }}-${{ github.event.pull_request.number }}"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace(path: str, old: str, new: str, *, count: int = -1) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"expected text missing from {path}: {old[:80]!r}")
    write(path, text.replace(old, new, count))


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def patch_gate() -> None:
    path = "actions/codex-review-gate/codex-review-gate.sh"
    replace(
        path,
        'has_trigger_clean_reaction() {\n  [[ -n "$COMMENT_ID" ]] || find_trigger_comment\n'
        '  [[ -n "$COMMENT_ID" ]] || return 1\n',
        'has_trigger_clean_reaction() {\n  COMMENT_ID=""\n  COMMENT_CREATED_AT=""\n'
        '  if ! find_bot_trigger_comment; then\n    return 2\n  fi\n'
        '  [[ -n "$COMMENT_ID" ]] || return 1\n',
    )


def commit_action_revision() -> str:
    run("git", "config", "user.name", "github-actions[bot]")
    run(
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    run("git", "add", "actions/codex-review-gate/codex-review-gate.sh")
    run("git", "commit", "-m", "fix: bind bootstrap review evidence to exact revision")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def repin(new_ref: str) -> None:
    tracked = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    for raw in tracked:
        if not raw:
            continue
        path = Path(raw.decode())
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD_REF in text:
            path.write_text(text.replace(OLD_REF, new_ref), encoding="utf-8")


def patch_validator() -> None:
    path = "ai_native.py"
    replace(
        path,
        '    if config is None:\n        return True\n',
        '    if config is None:\n        return False\n',
        count=1,
    )
    replace(
        path,
        '    if types is None:\n        return True\n'
        '    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):\n'
        '        return required <= {str(item) for item in types}\n',
        '    if types is None:\n        return False\n'
        '    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):\n'
        '        return required <= {str(item) for item in types}\n',
        count=1,
    )
    replace(
        path,
        '    workflow_path = root / relative\n    if not workflow_path.is_file():\n',
        '    workflow_path = root / relative\n'
        '    if workflow_path.is_symlink():\n'
        '        return [\n'
        '            Finding(\n'
        '                "evidence.ai_review_workflow_invalid",\n'
        '                "AI review workflow must be a regular file, not a symlink.",\n'
        '                path_name,\n'
        '            )\n'
        '        ]\n'
        '    if not workflow_path.is_file():\n',
    )
    replace(
        path,
        '        if "container" in job:\n'
        '            failures.append(f"{label} job must not declare a container")\n'
        '        if "strategy" in job:\n',
        '        if "container" in job:\n'
        '            failures.append(f"{label} job must not declare a container")\n'
        '        if "services" in job:\n'
        '            failures.append(f"{label} job must not declare services")\n'
        '        if "strategy" in job:\n',
    )
    replace(
        path,
        '    if not isinstance(concurrency, Mapping) or concurrency.get("cancel-in-progress") is not True:\n'
        '        failures.append("concurrency must cancel superseded runs")\n',
        '    if not isinstance(concurrency, Mapping) or concurrency.get("cancel-in-progress") is not False:\n'
        '        failures.append("concurrency must preserve active review polling")\n',
    )


def patch_codeowners() -> None:
    path = ".github/CODEOWNERS"
    text = read(path)
    text = text.replace("* @fatmambot33\n", "", 1)
    anchor = "/.github/workflows/** @fatmambot33\n"
    if anchor not in text:
        raise RuntimeError("CODEOWNERS workflow anchor missing")
    text = text.replace(
        anchor,
        anchor + "/.github/scripts/** @fatmambot33\n/tools/** @fatmambot33\n",
        1,
    )
    write(path, text)


def patch_docs() -> None:
    path = "docs/AI_REVIEW_GOVERNANCE.md"
    text = read(path)
    text = text.replace(
        "PR-scoped concurrency uses the evaluated `${{ github.event_name }}` and "
        "`${{ github.event.pull_request.number }}` expressions so separate PRs and "
        "separate request/wait event classes cannot cancel one another accidentally.",
        "PR-scoped concurrency still separates event classes and pull requests, but "
        "cancellation is disabled. A merge-ready polling run therefore remains active "
        "when another event for the same pull request arrives.",
    )
    text = text.replace(
        "The CODEOWNERS patterns are intentionally narrow, so ordinary source, "
        "documentation, and test changes still require zero human approvals. "
        "Governance/workflow changes are exceptional and require a fresh code-owner "
        "review or an explicitly authorized repository-owner bypass.",
        "The CODEOWNERS patterns are intentionally narrow. This reference repository "
        "protects workflows, governance code, `.github/scripts/**`, and `tools/**`, "
        "while ordinary source, documentation, and test changes remain outside those "
        "code-owner rules. Governance and privileged automation changes are exceptional "
        "and require a fresh code-owner review or an explicitly authorized "
        "repository-owner bypass.",
    )
    text = text.replace(
        "The one-time bootstrap path also accepts an unedited request from an `OWNER`, "
        "`MEMBER`, or `COLLABORATOR` when the new trusted `pull_request_target` workflow "
        "is not yet present on the default branch. The first line must be the exact "
        "`@codex review` command and the comment must contain the full current head/base "
        "marker. This is an explicitly privileged bootstrap exception rather than "
        "automated run provenance; request mode never creates or relies on it.",
        "The one-time bootstrap path accepts an unedited request from an `OWNER`, "
        "`MEMBER`, or `COLLABORATOR` when the new trusted `pull_request_target` workflow "
        "is not yet present on the default branch. The first line must be the exact "
        "`@codex review` command and the comment must contain the full current head/base "
        "marker. Bootstrap evidence is accepted only from a submitted Codex review "
        "whose GitHub `commit_id` matches the exact current HEAD and whose submission "
        "follows that request; reaction-only bootstrap evidence is never trusted. "
        "This is an explicitly privileged bootstrap exception rather than automated "
        "run provenance; request mode never creates or relies on it.",
    )
    old_permissions = """# trusted pull_request_target request job only
permissions:
  contents: read
  issues: write
  pull-requests: read
```

The required `codex-review` job additionally reads issue/review state but has no write scope."""
    new_permissions = """# trusted pull_request_target request job only
permissions:
  actions: read
  contents: read
  issues: write
  pull-requests: read

# required pull_request / pull_request_review wait job
permissions:
  actions: read
  contents: read
  issues: read
  pull-requests: read
```

Both jobs need `actions: read` to verify GitHub-hosted workflow-run provenance, including in private repositories. The required `codex-review` job has no write scope."""
    if old_permissions not in text:
        raise RuntimeError("documentation permissions block missing")
    write(path, text.replace(old_permissions, new_permissions))


def patch_workflow_local() -> None:
    replace(
        ".github/workflows/codex-review.yml",
        "  cancel-in-progress: true\n",
        "  cancel-in-progress: false\n",
    )


def patch_tests() -> None:
    for path in (
        "tests/test_ai_review_governance_hardening.py",
        "tests/test_validation.py",
    ):
        text = read(path).replace(
            "  cancel-in-progress: true\n",
            "  cancel-in-progress: false\n",
        )
        write(path, text)

    path = "tests/test_ai_review_governance_hardening.py"
    text = read(path)
    additions = r'''


def test_review_gate_requires_explicit_pr_activity_types(tmp_path: Path) -> None:
    full_types = (
        "  pull_request:\n"
        "    types: [opened, synchronize, reopened, ready_for_review, edited, labeled]\n"
    )
    workflow = WORKFLOW.replace(full_types, "  pull_request:\n", 1)
    _write_repository(tmp_path, workflow)
    assert any(
        "opened, synchronize, reopened" in item.message
        for item in _findings(tmp_path)
    )


def test_review_gate_rejects_job_services(tmp_path: Path) -> None:
    services = (
        "    runs-on: ubuntu-latest\n"
        "    services:\n"
        "      attacker:\n"
        "        image: attacker/image:latest\n"
    )
    workflow = WORKFLOW.replace("    runs-on: ubuntu-latest\n", services, 1)
    _write_repository(tmp_path, workflow)
    assert any("must not declare services" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_symlinked_workflow(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    workflow = tmp_path / ".github" / "workflows" / "codex-review.yml"
    target = tmp_path / "trusted-looking.yml"
    target.write_text(WORKFLOW, encoding="utf-8")
    workflow.unlink()
    workflow.symlink_to(target)
    assert any(
        "regular file, not a symlink" in item.message for item in _findings(tmp_path)
    )
'''
    if "test_review_gate_rejects_job_services" not in text:
        text += additions
    write(path, text)

    path = "tests/test_codex_review_gate.py"
    text = read(path)
    old = '''def test_bootstrap_clean_reaction_requires_trusted_unedited_head_marker() -> None:\n    script = GATE.read_text(encoding="utf-8")\n    bootstrap = _function_body(script, "find_bootstrap_trigger_comment")\n\n    assert '(.author_association // "") == "OWNER"' in bootstrap\n    assert '(.author_association // "") == "MEMBER"' in bootstrap\n    assert '(.author_association // "") == "COLLABORATOR"' in bootstrap\n    assert '(.created_at // "") == (.updated_at // "")' in bootstrap\n    assert 'test("^@codex review' in bootstrap\n    assert "contains($marker)" in bootstrap\n'''
    new = '''def test_bootstrap_reaction_is_not_accepted_as_clean_evidence() -> None:\n    script = GATE.read_text(encoding="utf-8")\n    bootstrap = _function_body(script, "find_bootstrap_trigger_comment")\n    reaction = _function_body(script, "has_trigger_clean_reaction")\n    review = _function_body(script, "has_matching_review")\n\n    assert '(.author_association // "") == "OWNER"' in bootstrap\n    assert "find_bot_trigger_comment" in reaction\n    assert "find_trigger_comment" not in reaction\n    assert "find_trigger_comment" in review\n    assert '(.commit_id // "") == $head' in review\n    assert ".submitted_at" in review\n'''
    if old not in text:
        raise RuntimeError("bootstrap regression test block missing")
    write(path, text.replace(old, new, 1))


def cleanup_script() -> None:
    run("git", "rm", "-f", ".github/scripts/tmp_final_codex_fixes.py")


def validate() -> None:
    run("python", "-m", "pip", "install", "--disable-pip-version-check", "-e", ".[dev]")
    run(
        "ruff",
        "format",
        "tests/test_ai_review_governance_hardening.py",
        "tests/test_validation.py",
        "tests/test_codex_review_gate.py",
    )
    run("ruff", "check", ".")
    run("pytest")
    run("python", "validator/validate_standard.py")
    run(
        "python",
        "-m",
        "ai_native",
        "validate",
        "fixtures/consumer-repository/AI_NATIVE_PLATFORM.yaml",
        "--root",
        "fixtures/consumer-repository",
    )
    run("bash", "-n", "actions/codex-review-gate/codex-review-gate.sh")
    run("python", "-m", "build")
    run("git", "diff", "--check")


def main() -> None:
    patch_gate()
    action_sha = commit_action_revision()
    repin(action_sha)
    patch_validator()
    patch_codeowners()
    patch_docs()
    patch_workflow_local()
    patch_tests()
    cleanup_script()
    validate()

    run(
        "git",
        "add",
        "-A",
        "--",
        ":!.github/workflows/codex-review.yml",
        ":!.github/workflows/tmp-final-codex-fixes.yml",
    )
    run("git", "commit", "-m", "fix: close final Codex governance findings")
    run("git", "push", "origin", "HEAD:align/codex-governance")
    print(f"ACTION_SHA={action_sha}")
    print(f"WORKFLOW_GROUP={GROUP}")


if __name__ == "__main__":
    main()
