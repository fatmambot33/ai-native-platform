# Changelog

All notable changes are documented here.

## Unreleased

### Added

- Add opt-in `evidence.paths.ai_review_workflow` governance evidence with structural validation of trusted current-HEAD Codex review workflows.
- Add a reusable Codex review gate that binds automated clean-reaction requests to the exact PR HEAD through server-verified GitHub Actions request-run provenance scoped to both head and base revisions.

### Security

- Require request jobs to use least-privilege permissions, keep wait jobs read-only, preserve the `codex-review` check name, and reject job-level concurrency/timeouts that can bypass or destabilize the gate.
- Require full pull-request activity coverage, direct `.github/workflows` placement, valid CODEOWNERS identities below GitHub's size limit, workflow-namespace ownership, executable runner declarations, and ownership of the reusable gate implementation plus registry-controlled executable validation pins.
- Keep bootstrap evidence fail-closed: collaborator-authored bootstrap markers are not trusted; bootstrap succeeds only through an exact-HEAD native Codex review bound to the active base or trusted bot request evidence bound to the exact HEAD and base revisions.

### Migration

- Consumers opting into `ai_review_workflow` must pin the gate action to an immutable trusted framework commit, protect `/.github/workflows/**` and `/.github/CODEOWNERS`, require the `codex-review` check, finish deterministic CI before spending the one-shot Codex review request, enable code-owner review with stale approvals dismissed on new pushes, and keep conversation resolution enabled.


## [0.3.0] - 2026-09-11

### Added

- Add manifest v2 with first-class `agent.skills.welcome` and `agent.skills.troubleshooting` capabilities.
- Require repository evidence for welcome and troubleshooting behavior when a v2 product exposes a plugin or MCP agent surface.
- Add an optional, off-by-default LLM self-improvement analysis layer with bounded repository evidence, strict structured output, deterministic grounding and confidence checks, a shared issue budget, and fail-soft behavior when credentials or the model are unavailable.
- Add a deterministic, capacity-limited product-roadmap workflow that maintains Now/Next/Later labels and a live dashboard issue from GitHub issues, with human P0/P1/P2 overrides.

### Changed

- Bump the canonical starter manifest to version 2 while continuing to validate pinned manifest-v1 consumers.
- Define guided onboarding and deterministic recovery as AI-native principles without requiring a Codex-specific file layout.
- License the standard and validator under Apache-2.0 and align package metadata.
- Make the unauthenticated, immutable public reusable workflow the primary documented distribution path.
- Keep authenticated workflow access as an optional private-mirror path rather than the default.

### Migration

- Run `ai-native upgrade AI_NATIVE_PLATFORM.yaml --diff` to migrate manifest v1 to v2.
- Add or retain repository-backed welcome and troubleshooting behavior under `agent.skills`.
- For products with `interfaces.plugin: true` or `interfaces.mcp: true`, point `evidence.paths.welcome_skill` and `evidence.paths.troubleshooting_skill` at real repository evidence. Packaged skill files are recommended but not required; commands, playbooks, or equivalent deterministic implementations are valid.
- The starter migration uses `skills/welcome/SKILL.md` and `skills/troubleshooting/SKILL.md` as conventional evidence paths; create them or replace those paths before validation.
- Existing manifest-v1 consumers pinned to earlier immutable contract refs remain valid until they opt into v2.

### Security

- Welcome and troubleshooting capabilities must preserve local-only secret handling and safe recovery behavior through repository-backed evidence.
- Publish CodeQL results automatically when the repository is public while retaining SARIF artifacts in all visibility modes.
- Document GitHub private vulnerability reporting and a non-public fallback contact path.

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
