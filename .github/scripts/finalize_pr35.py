"""Apply the final focused governance remediations for PR #35."""

from pathlib import Path


def _replace_function(text: str, start: str, end: str, replacement: str) -> str:
    """Replace one function body bounded by the next function declaration."""
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + replacement.rstrip() + "\n\n" + text[end_index:]


core = Path("ai_native.py")
core_text = core.read_text(encoding="utf-8")
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

    probes = (
        ".github/workflows/__ai_native_namespace_probe__.yml",
        ".github/workflows/nested/__ai_native_namespace_probe__.yml",
    )
    for pattern, owners in active_rules[namespace_index + 1 :]:
        normalized = pattern.lstrip("/")
        matcher = _codeowners_pattern_regex(pattern)
        targets_workflows = (
            normalized == ".github/workflows"
            or normalized.startswith(".github/workflows/")
            or "/" not in normalized
            or (
                matcher is not None
                and any(matcher.fullmatch(probe) for probe in probes)
            )
        )
        if targets_workflows and (
            not owners or not all(_valid_codeowner(owner) for owner in owners)
        ):
            return False
    return True''',
)
core.write_text(core_text, encoding="utf-8")

validator = Path("validator/validate_standard.py")
validator_text = validator.read_text(encoding="utf-8")
needle = '        ".github/CODEOWNERS",\n'
if '        ".github/dependabot.yml",\n' not in validator_text:
    if needle not in validator_text:
        raise SystemExit("governed_paths insertion point missing")
    validator_text = validator_text.replace(
        needle,
        needle + '        ".github/dependabot.yml",\n',
        1,
    )
validator.write_text(validator_text, encoding="utf-8")

codeowners = Path(".github/CODEOWNERS")
namespace_patterns = {
    "/.github/workflows/**",
    ".github/workflows/**",
    "/.github/workflows/",
    ".github/workflows/",
}
retained_lines: list[str] = []
for line in codeowners.read_text(encoding="utf-8").splitlines():
    parts = line.split()
    if parts and parts[0] in namespace_patterns:
        continue
    retained_lines.append(line)
retained_lines.append("/.github/workflows/** @fatmambot33")
codeowners.write_text("\n".join(retained_lines) + "\n", encoding="utf-8")

test_path = Path("tests/test_pr35_followup_regressions.py")
test_text = test_path.read_text(encoding="utf-8")
if "import ai_native\n" not in test_text:
    test_text = test_text.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport ai_native\n",
        1,
    )
regressions = '''


def test_workflow_namespace_owner_rule_rejects_later_ownerless_override(tmp_path: Path) -> None:
    """Reject a predictable-probe bypass after an ownerless workflow override."""
    github = tmp_path / ".github"
    github.mkdir(exist_ok=True)
    codeowners = github / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @fatmambot33\\n"
        "/.github/workflows/**\\n"
        "/.github/workflows/__ai_native_unmatched_probe__.yml @fatmambot33\\n",
        encoding="utf-8",
    )
    assert not ai_native._codeowners_has_workflow_namespace_rule(tmp_path)

    codeowners.write_text(
        "/.github/workflows/** @fatmambot33\\n"
        "/.github/CODEOWNERS @fatmambot33\\n",
        encoding="utf-8",
    )
    assert ai_native._codeowners_has_workflow_namespace_rule(tmp_path)


def test_dependabot_configuration_is_canonically_governed() -> None:
    """Keep Dependabot in the canonical governed-path self-check."""
    validator_text = (ROOT / "validator" / "validate_standard.py").read_text(
        encoding="utf-8"
    )
    assert '".github/dependabot.yml"' in validator_text
'''
if "test_workflow_namespace_owner_rule_rejects_later_ownerless_override" not in test_text:
    test_text += regressions
test_path.write_text(test_text, encoding="utf-8")
