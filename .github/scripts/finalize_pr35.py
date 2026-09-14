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
    """Return whether the final CODEOWNERS rule protects every workflow path."""
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
    if not active_rules:
        return False
    pattern, owners = active_rules[-1]
    return (
        pattern in accepted
        and bool(owners)
        and all(_valid_codeowner(owner) for owner in owners)
    )''',
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


def test_workflow_namespace_owner_rule_must_be_final_effective_rule(tmp_path: Path) -> None:
    """Reject a predictable-probe bypass after an ownerless workflow override."""
    github = tmp_path / ".github"
    github.mkdir()
    codeowners = github / "CODEOWNERS"
    codeowners.write_text(
        "/.github/workflows/** @fatmambot33\\n"
        "/.github/workflows/**\\n"
        "/.github/workflows/__ai_native_unmatched_probe__.yml @fatmambot33\\n",
        encoding="utf-8",
    )
    assert not ai_native._codeowners_has_workflow_namespace_rule(tmp_path)

    codeowners.write_text(
        codeowners.read_text(encoding="utf-8")
        + "/.github/workflows/** @fatmambot33\\n",
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
if "test_workflow_namespace_owner_rule_must_be_final_effective_rule" not in test_text:
    test_text += regressions
test_path.write_text(test_text, encoding="utf-8")
