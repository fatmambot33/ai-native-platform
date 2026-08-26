# Changelog

All notable changes are documented here.

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
