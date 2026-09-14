"""Apply the final focused Codex governance remediations for PR #35."""

from pathlib import Path

OLD_GATE_REF = "0c4f68f62abb426ba80d0d1bb36356c3468f5534"
NEW_GATE_REF = "0b5ce84c0d6560adffce4b1c32e08ba2a57de7ea"


def _replace_function(text: str, start: str, end: str, replacement: str) -> str:
    """Replace one function body bounded by the next function declaration."""
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


core = Path("ai_native.py")
core_text = core.read_text(encoding="utf-8")
if OLD_GATE_REF not in core_text:
    raise SystemExit("old trusted gate ref missing")
core_text = core_text.replace(OLD_GATE_REF, NEW_GATE_REF)

old_env_set = (
    'FORBIDDEN_GITHUB_CLI_ENV_KEYS = '
    'frozenset({"GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN"})'
)
new_env_set = (
    "MAX_AI_REVIEW_TIMING_SECONDS = 2_147_483_647\n"
    "FORBIDDEN_GITHUB_CLI_ENV_KEYS = frozenset(\n"
    '    {"GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "BASH_ENV"}\n'
    ")"
)
if old_env_set not in core_text:
    raise SystemExit("forbidden env declaration missing")
core_text = core_text.replace(old_env_set, new_env_set, 1)

core_text = _replace_function(
    core_text,
    "def _positive_integer_input(value: Any) -> bool:\n",
    "def _has_forbidden_github_cli_env(value: Any) -> bool:\n",
    '''def _positive_integer_input(value: Any) -> bool:
    """Return whether an action input is a bounded Bash-safe positive integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 < value <= MAX_AI_REVIEW_TIMING_SECONDS
    if isinstance(value, str):
        if re.fullmatch(r"[1-9][0-9]*", value) is None:
            return False
        limit = str(MAX_AI_REVIEW_TIMING_SECONDS)
        if len(value) > len(limit):
            return False
        if len(value) == len(limit) and value > limit:
            return False
        return True
    return False''',
)

core_text = core_text.replace(
    '"""Return whether declared env can redirect or re-authenticate GitHub CLI."""',
    '"""Return whether declared env can alter trusted gate execution or GitHub CLI."""',
    1,
)
core_text = core_text.replace(
    "workflow must not override GitHub CLI host or authentication environment",
    "workflow must not override trusted gate or GitHub CLI environment",
)
core_text = core_text.replace(
    "job must not override GitHub CLI host or authentication environment",
    "job must not override trusted gate or GitHub CLI environment",
)

core_text = _replace_function(
    core_text,
    "def _codeowners_has_workflow_namespace_rule(root: Path) -> bool:\n",
    "def _unowned_workflows(root: Path) -> list[str]:\n",
    '''def _codeowners_has_workflow_namespace_rule(root: Path) -> bool:
    """Return whether CODEOWNERS keeps the full workflow namespace protected."""
    codeowners = root / ".github" / "CODEOWNERS"
    if _path_has_symlink_component(root, Path(".github/CODEOWNERS")) or not codeowners.is_file():
        return False
    accepted = {
        "/.github/workflows/**",
        ".github/workflows/**",
        "/.github/workflows/",
        ".github/workflows/",
    }
    active_rules: list[tuple[str, list[str]]] = []
    for raw_line in codeowners.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts:
            active_rules.append((parts[0], parts[1:]))

    namespace_index: int | None = None
    for index, (pattern, owners) in enumerate(active_rules):
        if (
            pattern in accepted
            and bool(owners)
            and all(_valid_codeowner(owner) for owner in owners)
        ):
            namespace_index = index
    if namespace_index is None:
        return False

    fixed_probes = (
        ".github/workflows/__ai_native_namespace_probe__.yml",
        ".github/workflows/nested/__ai_native_namespace_probe__.yml",
        ".github/workflows/release-x.yml",
        ".github/workflows/release-x.yaml",
        ".github/workflows/ci.yml",
    )
    for pattern, owners in active_rules[namespace_index + 1 :]:
        normalized = pattern.lstrip("/")
        matcher = _codeowners_pattern_regex(pattern)
        derived_probe = None
        if matcher is not None:
            basename = normalized.rsplit("/", 1)[-1]
            basename = re.sub(r"\\[[^]]+\\]", "a", basename)
            basename = basename.replace("*", "x").replace("?", "x")
            if basename and "/" not in basename:
                derived_probe = f".github/workflows/{basename}"
        targets_workflows = (
            normalized == ".github/workflows"
            or normalized.startswith(".github/workflows/")
            or "/" not in normalized
            or (
                matcher is not None
                and any(matcher.fullmatch(probe) for probe in fixed_probes)
            )
            or (
                matcher is not None
                and derived_probe is not None
                and matcher.fullmatch(derived_probe) is not None
            )
        )
        if targets_workflows and (
            not owners or not all(_valid_codeowner(owner) for owner in owners)
        ):
            return False
    return True''',
)
core.write_text(core_text, encoding="utf-8")

workflow = Path(".github/workflows/codex-review.yml")
workflow_text = workflow.read_text(encoding="utf-8")
if OLD_GATE_REF not in workflow_text:
    raise SystemExit("old workflow gate ref missing")
workflow.write_text(workflow_text.replace(OLD_GATE_REF, NEW_GATE_REF), encoding="utf-8")

test_path = Path("tests/test_ai_review_governance_hardening.py")
test_text = test_path.read_text(encoding="utf-8")
if OLD_GATE_REF not in test_text:
    raise SystemExit("old test gate ref missing")
test_text = test_text.replace(OLD_GATE_REF, NEW_GATE_REF)

marker = "def test_review_gate_namespace_rule_must_remain_effective(tmp_path: Path) -> None:\n"
if marker not in test_text:
    raise SystemExit("test insertion point missing")
regressions = r'''

def test_review_gate_rejects_indirect_ownerless_workflow_override(tmp_path: Path) -> None:
    """Reject broad basename globs that can override future workflow ownership."""
    _write_repository(tmp_path)
    codeowners = tmp_path / ".github" / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @repository-owner\n"
        "**/release-*.yml\n"
        "/.github/workflows/codex-review.yml @repository-owner\n"
        "/.github/CODEOWNERS @repository-owner\n",
        encoding="utf-8",
    )
    assert any("namespace rule" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_huge_timing_without_conversion_error(tmp_path: Path) -> None:
    """Reject huge decimal timing strings without calling int on them first."""
    huge = "9" * 5000
    workflow = WORKFLOW.replace(
        "          mode: wait\n          request-label: codex:review\n",
        "          mode: wait\n          request-label: codex:review\n"
        f"          timeout-seconds: '{huge}'\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_timing_above_runtime_bound(tmp_path: Path) -> None:
    """Keep timing overrides inside the supported Bash arithmetic bound."""
    workflow = WORKFLOW.replace(
        "          mode: wait\n          request-label: codex:review\n",
        "          mode: wait\n          request-label: codex:review\n"
        "          timeout-seconds: '2147483648'\n",
    )
    _write_repository(tmp_path, workflow)
    assert any("positive timing overrides" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_workflow_bash_env(tmp_path: Path) -> None:
    """Reject workflow-level BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "permissions:\n  contents: read\n",
        "env:\n  BASH_ENV: /tmp/pwn\npermissions:\n  contents: read\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("trusted gate" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_job_bash_env(tmp_path: Path) -> None:
    """Reject job-level BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    env:\n      BASH_ENV: /tmp/pwn\n",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("trusted gate" in item.message for item in _findings(tmp_path))


def test_review_gate_rejects_step_bash_env(tmp_path: Path) -> None:
    """Reject gate-step BASH_ENV injection around trusted shell code."""
    workflow = WORKFLOW.replace(
        "      - uses: ",
        "      - env:\n          BASH_ENV: /tmp/pwn\n        uses: ",
        1,
    )
    _write_repository(tmp_path, workflow)
    assert any("canonical gate step" in item.message for item in _findings(tmp_path))
'''
if "test_review_gate_rejects_indirect_ownerless_workflow_override" not in test_text:
    test_text = test_text.replace(marker, regressions + "\n\n" + marker)
test_path.write_text(test_text, encoding="utf-8")
