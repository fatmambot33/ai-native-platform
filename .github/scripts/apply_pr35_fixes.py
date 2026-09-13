"""Apply the final PR #35 Codex governance remediation in an ephemeral CI checkout."""

from pathlib import Path

GATE_REF = "48f0c6c4351a040f3214ef01e036b5f00032b2cd"
OLD_REF = "96f34eeb234cb9c4cebf68749a8fcbca969f5865"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace exactly one expected anchor."""
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def update_conformance() -> None:
    """Harden static AI-review workflow conformance."""
    path = Path("ai_native.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    for key in ("timeout-seconds", "poll-seconds"):
        if key in inputs and not _positive_integer_input(inputs[key]):
            return None
    return uses[len(prefix) :]
''',
        '''    for key in ("timeout-seconds", "poll-seconds"):
        if key in inputs and not _positive_integer_input(inputs[key]):
            return None
    timeout = int(inputs.get("timeout-seconds", 1800))
    poll = int(inputs.get("poll-seconds", 60))
    if poll > timeout:
        return None
    return uses[len(prefix) :]
''',
        "timing validation",
    )

    helper = '''def _codeowners_has_workflow_namespace_rule(root: Path) -> bool:
    """Return whether CODEOWNERS explicitly protects the workflow namespace."""
    codeowners = root / ".github" / "CODEOWNERS"
    if _path_has_symlink_component(root, Path(".github/CODEOWNERS")) or not codeowners.is_file():
        return False
    accepted = {
        "/.github/workflows/**",
        ".github/workflows/**",
        "/.github/workflows/",
        ".github/workflows/",
    }
    for raw_line in codeowners.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts and parts[0] in accepted and parts[1:]:
            if all(_valid_codeowner(owner) for owner in parts[1:]):
                return True
    return False


def _unowned_workflows(root: Path) -> list[str]:
    """Return current workflow files lacking effective CODEOWNERS coverage."""
    directory = root / ".github" / "workflows"
    if not directory.is_dir() or directory.is_symlink():
        return [".github/workflows"]
    missing: list[str] = []
    for workflow in sorted(directory.iterdir()):
        if workflow.suffix not in {".yml", ".yaml"}:
            continue
        relative = workflow.relative_to(root)
        if (
            _path_has_symlink_component(root, relative)
            or not _codeowners_covers_path(root, relative)
        ):
            missing.append(relative.as_posix())
    return missing


'''
    signature = (
        "def _single_ai_review_workflow_findings(value: str, root: Path) -> list[Finding]:\n"
    )
    text = replace_once(
        text,
        signature,
        helper + signature,
        "workflow ownership helpers",
    )
    text = replace_once(
        text,
        '''    if not _codeowners_covers_path(
        root, Path(".github/workflows/__ai_native_required_check_probe__.yml")
    ):
        failures.append("the entire .github/workflows namespace must be CODEOWNERS-protected")
''',
        '''    if not _codeowners_has_workflow_namespace_rule(root):
        failures.append(
            "the entire .github/workflows namespace must be CODEOWNERS-protected "
            "by an explicit namespace rule"
        )
    unowned_workflows = _unowned_workflows(root)
    if unowned_workflows:
        failures.append(
            "every workflow must have effective CODEOWNERS coverage; missing: "
            + ", ".join(unowned_workflows)
        )
''',
        "workflow namespace validation",
    )
    text = text.replace(OLD_REF, GATE_REF)
    path.write_text(text, encoding="utf-8")


def update_refs() -> None:
    """Pin canonical consumers and regression fixtures to the hardened gate."""
    for name in (
        ".github/workflows/codex-review.yml",
        "tests/test_ai_review_governance_remaining.py",
        "tests/test_ai_review_governance_hardening.py",
        "tests/test_validation.py",
    ):
        path = Path(name)
        text = path.read_text(encoding="utf-8")
        if OLD_REF in text:
            path.write_text(text.replace(OLD_REF, GATE_REF), encoding="utf-8")


def update_validator() -> None:
    """Protect the new executable preflight in canonical self-validation."""
    path = Path("validator/validate_standard.py")
    text = path.read_text(encoding="utf-8")
    if '"actions/codex-review-gate/preflight.sh"' not in text:
        text = replace_once(
            text,
            '        "actions/codex-review-gate/codex-review-gate.sh",\n',
            '        "actions/codex-review-gate/codex-review-gate.sh",\n'
            '        "actions/codex-review-gate/preflight.sh",\n',
            "preflight governed path",
        )
        path.write_text(text, encoding="utf-8")


def add_regressions() -> None:
    """Add focused coverage for the five fresh Codex findings."""
    path = Path("tests/test_ai_review_governance_remaining.py")
    text = path.read_text(encoding="utf-8")
    if "test_preflight_binds_marker_context_to_base_and_custom_context" in text:
        return
    text += r'''


def test_preflight_binds_marker_context_to_base_and_custom_context() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert 'export CODEX_REVIEW_CONTEXT="${BASE_SHA}:${CUSTOM_CONTEXT}"' in source


def test_preflight_verifies_codeowners_with_github() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert 'repos/${REPO}/codeowners/errors?ref=${HEAD_SHA}' in source
    assert "verify_codeowners" in source


def test_request_and_wait_requires_explicit_review_label() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert '[[ "$MODE" == "request-and-wait" ]]' in source
    assert "event_label" in source
    assert 'explicit ${REQUEST_LABEL} label event' in source


def test_preflight_clamps_polling_to_timeout() -> None:
    source = Path("actions/codex-review-gate/preflight.sh").read_text(encoding="utf-8")
    assert 'if (( POLL_SECONDS > TIMEOUT_SECONDS )); then' in source
    assert 'POLL_SECONDS="$TIMEOUT_SECONDS"' in source


def test_review_gate_rejects_poll_interval_longer_than_timeout(tmp_path: Path) -> None:
    workflow = WORKFLOW.replace(
        "          request-label: codex:review\n",
        (
            "          request-label: codex:review\n"
            "          timeout-seconds: 30\n"
            "          poll-seconds: 3600\n"
        ),
        2,
    )
    _write_repository(tmp_path, workflow)
    assert _findings(tmp_path)


def test_review_gate_requires_namespace_wide_codeowners_rule(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("namespace rule" in item.message for item in _findings(tmp_path))


def test_review_gate_checks_every_existing_workflow_owner(tmp_path: Path) -> None:
    _write_repository(tmp_path)
    extra = tmp_path / ".github" / "workflows" / "bypass.yml"
    extra.write_text("name: bypass\non: push\njobs: {}\n", encoding="utf-8")
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        codeowners.read_text(encoding="utf-8") + "/.github/workflows/bypass.yml\n",
        encoding="utf-8",
    )
    assert any("bypass.yml" in item.message for item in _findings(tmp_path))
'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    """Apply all deterministic remediation edits."""
    update_conformance()
    update_refs()
    update_validator()
    add_regressions()


if __name__ == "__main__":
    main()
