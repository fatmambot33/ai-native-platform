"""Apply the final Codex governance remediations to PR #35."""

from __future__ import annotations

import json
import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    """Replace exactly one occurrence or fail closed."""
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


path = Path("ai_native.py")
text = path.read_text(encoding="utf-8")

marker = '''TRUSTED_AI_REVIEW_GATE_REFS = frozenset(
    {
        "96f34eeb234cb9c4cebf68749a8fcbca969f5865",
    }
)
'''
if "PR_EVENT_FILTER_KEYS" not in text:
    text = replace_once(
        text,
        marker,
        marker
        + '''PR_EVENT_FILTER_KEYS = frozenset(
    {"branches", "branches-ignore", "paths", "paths-ignore"}
)
FORBIDDEN_GITHUB_CLI_ENV_KEYS = frozenset(
    {"GITHUB_TOKEN", "GITHUB_ENTERPRISE_TOKEN"}
)
''',
        "governance constants",
    )

text = replace_once(
    text,
    '''    if not isinstance(config, Mapping):
        return False
    types = config.get("types")
    if types is None:
        return False
    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):
        return required <= {str(item) for item in types}
    return False
''',
    '''    if not isinstance(config, Mapping):
        return False
    if any(key in config for key in PR_EVENT_FILTER_KEYS):
        return False
    types = config.get("types")
    if types is None:
        return False
    if isinstance(types, Sequence) and not isinstance(types, (str, bytes)):
        return required <= {str(item) for item in types}
    return False
''',
    "pull_request filters",
)

text = replace_once(
    text,
    '''    config = events[event_name]
    if not isinstance(config, Mapping):
        return False
    types = config.get("types")
    if isinstance(types, str):
        return types == "labeled"
''',
    '''    config = events[event_name]
    if not isinstance(config, Mapping):
        return False
    if any(key in config for key in PR_EVENT_FILTER_KEYS):
        return False
    types = config.get("types")
    if isinstance(types, str):
        return types == "labeled"
''',
    "pull_request_target filters",
)

cli_helper = '''def _has_forbidden_github_cli_env(value: Any) -> bool:
    """Return whether declared env can redirect or re-authenticate GitHub CLI."""
    if not isinstance(value, Mapping):
        return False
    for key in value:
        normalized = str(key).upper()
        if normalized.startswith("GH_") or normalized in FORBIDDEN_GITHUB_CLI_ENV_KEYS:
            return True
    return False


'''
gate_marker = "def _gate_ref(job: Mapping[str, Any], mode: str) -> str | None:\n"
if cli_helper not in text:
    text = replace_once(text, gate_marker, cli_helper + gate_marker, "CLI env helper")

text = replace_once(
    text,
    '''    step = steps[0]
    if "if" in step or step.get("continue-on-error") not in (None, False):
        return None
''',
    '''    step = steps[0]
    if "if" in step or step.get("continue-on-error") not in (None, False):
        return None
    if _has_forbidden_github_cli_env(step.get("env")):
        return None
''',
    "gate step env",
)

symlink_helper = '''def _path_has_symlink_component(root: Path, relative: Path) -> bool:
    """Return whether any repository-relative path component is a symlink."""
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


'''
codeowners_marker = (
    "def _codeowners_effective_owners(root: Path, relative: Path) -> list[str] | None:\n"
)
if symlink_helper not in text:
    text = replace_once(
        text,
        codeowners_marker,
        symlink_helper + codeowners_marker,
        "symlink helper",
    )

text = replace_once(
    text,
    '''    codeowners = root / ".github" / "CODEOWNERS"
    if not codeowners.is_file():
        return None
''',
    '''    codeowners_relative = Path(".github/CODEOWNERS")
    codeowners = root / codeowners_relative
    if _path_has_symlink_component(root, codeowners_relative) or not codeowners.is_file():
        return None
''',
    "CODEOWNERS symlink protection",
)

text = replace_once(
    text,
    '''    workflow_path = root / relative
    if workflow_path.is_symlink():
''',
    '''    workflow_path = root / relative
    if _path_has_symlink_component(root, relative):
''',
    "workflow ancestor symlinks",
)

text = replace_once(
    text,
    '''    failures: list[str] = []
    events = _workflow_events(workflow)
''',
    '''    failures: list[str] = []
    if _has_forbidden_github_cli_env(workflow.get("env")):
        failures.append(
            "workflow must not override GitHub CLI host or authentication environment"
        )
    events = _workflow_events(workflow)
''',
    "workflow env",
)

text = replace_once(
    text,
    '''        if "concurrency" in job:
            failures.append(f"{label} job must not override workflow concurrency")
    if wait.get("name") not in (None, "codex-review"):
''',
    '''        if "concurrency" in job:
            failures.append(f"{label} job must not override workflow concurrency")
        if _has_forbidden_github_cli_env(job.get("env")):
            failures.append(
                f"{label} job must not override GitHub CLI host or authentication environment"
            )
    if wait.get("name") not in (None, "codex-review"):
''',
    "job env",
)

pattern = re.compile(
    r"def _ai_review_workflow_findings\(value: Any, root: Path\) -> list\[Finding\]:\n"
    r".*?\n\n\ndef evidence_findings",
    re.S,
)
replacement = '''def _ai_review_workflow_findings(value: Any, root: Path) -> list[Finding]:
    """Validate the single explicitly declared trusted AI-review workflow."""
    path_name = "evidence.paths.ai_review_workflow"
    if not isinstance(value, str) or not value:
        return [
            Finding(
                "evidence.ai_review_workflow_invalid",
                "AI review evidence must be exactly one nonempty workflow path string.",
                path_name,
            )
        ]
    return _single_ai_review_workflow_findings(value, root)


def evidence_findings'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise RuntimeError(f"workflow declaration function: expected one match, found {count}")
path.write_text(text, encoding="utf-8")

schema_path = Path("schemas/ai-native-platform.schema.json")
schema = json.loads(schema_path.read_text(encoding="utf-8"))
schema["properties"]["evidence"]["properties"]["paths"]["properties"][
    "ai_review_workflow"
] = {"type": "string", "minLength": 1}
schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

validator_path = Path("validator/validate_standard.py")
validator = validator_path.read_text(encoding="utf-8")
if '"docs/AI_REVIEW_GOVERNANCE.md",' not in validator:
    validator = replace_once(
        validator,
        '        "docs/GOVERNANCE.md",\n        "pyproject.toml",',
        '        "docs/GOVERNANCE.md",\n'
        '        "docs/AI_REVIEW_GOVERNANCE.md",\n'
        '        "pyproject.toml",',
        "governed AI-review policy",
    )
validator_path.write_text(validator, encoding="utf-8")
