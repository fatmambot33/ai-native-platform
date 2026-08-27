# Changelog

All notable changes are documented here.

## Unreleased

### Added

- Add an optional, off-by-default LLM self-improvement analysis layer with bounded repository evidence, strict structured output, deterministic grounding and confidence checks, a shared issue budget, and fail-soft behavior when credentials or the model are unavailable.

### Changed

- License the standard and validator under Apache-2.0 and align package metadata.
- Make the unauthenticated, immutable public reusable workflow the primary documented distribution path.
- Keep authenticated workflow access as an optional private-mirror path rather than the default.

### Security

- Publish CodeQL results automatically when the repository is public while retaining SARIF artifacts in all visibility modes.
- Document GitHub private vulnerability reporting and a non-public fallback contact path.

## [0.3.0] - 2026-08-27

### Added

- Define current-HEAD AI review as a first-class merge-governance invariant for AI-native repositories.
- Add the reusable `actions/codex-review-gate` composite action for Codex review enforcement.
- Add a two-phase review flow that requests Codex before validation and waits for current-HEAD evidence only after normal validation work has run.
- Add repository evidence for the protected workflow that enforces AI review governance.
- Document the solo-maintainer model: zero required human approvals for ordinary changes, current-HEAD Codex review, required review-thread resolution, and compatibility with auto-merge.

### Changed

- Treat any new PR commit as invalidating older Codex review evidence.
- Match Codex review evidence to the full GitHub review `commit_id`; clean-review reactions are accepted only on a HEAD-specific review request.
- Paginate GitHub review/comment/reaction reads and poll conservatively to stay within GitHub API budgets.

### Security

- Scope `issues: write` to the validation job only, for posting the HEAD-specific `@codex review` request.
- Fail safely for fork and Dependabot contexts where the pull-request token cannot post comments; maintainers can supply the same exact-command, HEAD-scoped request manually.

## [0.2.0] - 2026-08-26

### Changed

- **Breaking:** replace `evidence.paths.security_workflow` with `evidence.paths.security_evidence` when `quality.security_scan` is enabled. The old key is not accepted as an alias.
- Security evidence is now implementation-neutral: consumers may point to a security workflow or to repository documentation proving native GitHub CodeQL, ruleset, or default-setup enforcement.
- `interfaces.mcp` is optional to declare. When present as `true`, MCP repository evidence is still required.
- The `agent-tool` profile still requires at least one agent surface: plugin or MCP. Plugin-only consumers do not need to declare `mcp: false`.
- The starter manifest no longer implies that a custom CodeQL workflow is mandatory.

### Migration

- Rename `security_workflow` to `security_evidence` in `AI_NATIVE_PLATFORM.yaml`.
- Keep the existing evidence path if it points to a real security workflow, or point the new key to a repository evidence document for native ruleset/default-setup scanning.
- Consumers without an MCP surface may omit `interfaces.mcp` entirely.
- Pin consumers to the immutable v0.2 contract before validation.

## [0.1.0] - 2026-08-06

### Added

- Profile-aware manifest contract and evidence-backed validator.
- Installable `ai-native` CLI.
- JSON and SARIF conformance output.
- Deterministic legacy-manifest migration with dry-run and diff.
- Passing and failing repository fixtures for all six profiles.
- Immutable registry and continuous conformance checks for three real consumer repositories.
- Vendored-contract distribution proven in PermutiveAPI, MatplotLibAPI, and openai-sdk-helpers.
- Bounded evidence-driven self-improvement with redaction, suppression, fingerprinting, and issue budgets.
- SHA-256 checksums, SPDX SBOM, verified SLSA-compatible provenance, and conditional GitHub-hosted attestations.
- Idempotent verified-main release workflow that creates the immutable tag and GitHub prerelease.

### Security

- Local-only credential contract and credential fixture.
- CodeQL v4 analysis with reviewed retained SARIF across the standard and registered consumers.
- Secret redaction for normalized improvement signals.
- Private-release provenance verification independent of GitHub's plan-limited attestations API.

### Distribution

- Immutable vendored-contract snapshots are the proven default for public consumers.
- Private reusable workflows remain available where repository Actions access and a read-only token are configured.
- Production consumers pin `v0.1.0` or an immutable commit; floating `main` references are prohibited.
