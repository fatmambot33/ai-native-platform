## Summary

Describe the scoped change and why it is needed.

## Evidence

Link the issue, failing check, measurement, or repository finding that motivated the change.

## Contract impact

- [ ] No manifest or schema impact
- [ ] Backward-compatible contract change
- [ ] Breaking contract change with migration notes

## Validation

- [ ] `ruff check .`
- [ ] `pytest`
- [ ] `python validator/validate_standard.py`
- [ ] `python -m build`

## Governance

- [ ] This change does not expand credentials, permissions, security-sensitive behavior, public APIs, or release scope
- [ ] Human approval has been requested for any high-impact change
