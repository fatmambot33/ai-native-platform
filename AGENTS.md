# Agent Instructions

## Mission

Keep this repository a small, authoritative AI-native standard and conformance tool. Do not turn it into a general runtime framework.

## Sources of truth

- Product contract: `schemas/ai-native-platform.schema.json`
- Standard identity and profiles: `standard/AI_NATIVE_PLATFORM.yaml`
- Human target state: `CHECKLIST.md`
- Execution order: `ROADMAP.md`
- Autonomy policy: `docs/GOVERNANCE.md`

## Required checks

Run before opening or updating a pull request:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
python validator/validate_standard.py
python -m build
```

## Change rules

- Add or update tests for every contract or validator change.
- Keep schema, templates, documentation, and migration notes synchronized.
- Use exact release tags or commit SHAs in examples.
- Never weaken evidence requirements merely to make a repository pass.
- Require human approval for breaking, security, credential, permission, public API, and release changes.
