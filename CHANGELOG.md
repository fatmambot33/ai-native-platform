# Changelog

All notable changes are documented here.

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
