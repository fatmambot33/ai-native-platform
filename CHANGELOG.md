# Changelog

All notable changes are documented here.

## [0.1.0] - 2026-08-06

### Added

- Profile-aware manifest contract and evidence-backed validator.
- Installable `ai-native` CLI.
- JSON and SARIF conformance output.
- Deterministic legacy-manifest migration with dry-run and diff.
- Passing and failing repository fixtures for all six profiles.
- Dedicated private consumer repository fixture.
- Bounded evidence-driven self-improvement with redaction, suppression, fingerprinting, and issue budgets.
- SHA-256 checksums, SPDX SBOM, SLSA-compatible provenance inputs, and GitHub build attestations.
- Immutable tag-driven release workflow.

### Security

- Local-only credential contract and credential fixture.
- CodeQL v4 analysis with retained SARIF.
- Secret redaction for normalized improvement signals.

### Distribution

- `v0.1.0` uses private distribution and exact version pinning.
