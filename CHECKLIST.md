# First-Class AI-Native Platform Checklist

A repository is compliant only when its manifest declarations are backed by repository evidence.

## Product and packaging

- [ ] Installable Python package with `pyproject.toml`
- [ ] PyPI installation documented
- [ ] Git installation documented
- [ ] Editable development installation documented
- [ ] Clean package build and installation validated in CI

## Plugin surface

- [ ] Public, versioned plugin contract
- [ ] Typed plugin protocol or abstract base
- [ ] Deterministic registration and discovery
- [ ] Capability metadata
- [ ] Codex plugin manifest
- [ ] Git-backed Codex marketplace catalog
- [ ] Plugin contract tests

## Typing and schemas

- [ ] Public API is typed
- [ ] `py.typed` is packaged, or an equivalent explicit typing contract exists
- [ ] Strict type checking runs in CI
- [ ] Tool inputs and outputs have machine-readable schemas
- [ ] Structured outputs are deterministic

## Installation and configuration

- [ ] README contains quick-start installation
- [ ] Credentialed products provide `.env.example`
- [ ] Credentials remain local and are ignored by Git
- [ ] Credentialed products provide guided `configure` and `doctor` commands
- [ ] Secret values are never echoed, logged, or remotely stored

## Documentation

- [ ] README quick start
- [ ] Plugin installation and usage guide
- [ ] API or SDK documentation
- [ ] Runnable examples
- [ ] Architecture or design documentation
- [ ] `AGENTS.md` contribution guidance for coding agents

## Quality and safety

- [ ] Unit and integration tests
- [ ] Plugin discovery and lifecycle tests
- [ ] Packaging smoke test
- [ ] Compatibility checks
- [ ] Security scanning
- [ ] Human confirmation for writes or destructive actions

## Self-improvement

- [ ] GitHub Issues are the work queue
- [ ] Agent-ready issue template exists
- [ ] Improvement discovery workflow exists
- [ ] Agent may prepare a pull request
- [ ] CI is required before merge
- [ ] Breaking, security, credential, public API, permission, and release changes require human approval
