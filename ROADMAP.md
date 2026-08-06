# Roadmap

## Phase 0 — Truthful foundation

Status: **complete**

- [x] Correct repository metadata, issue forms, templates, and workflow naming.
- [x] Document immutable references and supported distribution modes.

## Phase 1 — Authoritative contract

Status: **complete**

- [x] Enforce JSON Schema draft 2020-12.
- [x] Use profile-aware rules and explicit repository evidence.
- [x] Reject unknown controlled fields while retaining `extensions`.

## Phase 2 — Conformance product

Status: **complete for v0.1.0**

- [x] Provide `init`, `validate`, `score`, and `doctor`.
- [x] Provide JSON and SARIF output.
- [x] Provide deterministic `upgrade` with dry-run and diff.
- [x] Add passing and focused failing fixtures for every profile.
- [x] Exercise local credential requirements.
- [x] Test stable finding codes on Python 3.10 and 3.12.

## Phase 3 — Trustworthy release

Status: **complete for v0.1.0**

- [x] Support immutable vendored-contract consumption and optional private reusable workflows.
- [x] Register and continuously validate three real consumers.
- [x] Build wheel and source artifacts.
- [x] Generate and verify SHA-256 checksums and SPDX SBOM.
- [x] Generate SLSA-compatible provenance and verify artifact subject digests before publication.
- [x] Publish GitHub-hosted attestations automatically when repository visibility and plan support them.
- [x] Retain reviewed CodeQL SARIF where alert publication is unavailable or already managed by default setup.
- [x] Create the immutable `v0.1.0` tag from a verified `main` commit.
- [x] Publish an idempotent GitHub prerelease only after standard and consumer gates pass.
- [x] Record rollback, revocation, and recovery guidance.

### Repository-plan controls

GitHub reports that protected-branch rulesets are unavailable for this private repository on the
current plan. GitHub also reports that hosted attestations are unavailable for user-owned private
repositories. v0.1 therefore enforces the release criteria inside the idempotent release workflow
and publishes independently verifiable checksums, SPDX SBOM, and SLSA-compatible provenance as
release assets. If visibility or plan capabilities change, branch protection and hosted attestations
activate as additional controls without changing the contract.

## Phase 4 — Evidence-driven self-improvement

Status: **complete for read-only discovery and issue creation**

- [x] Detect canonical, fixture, consumer, and release drift.
- [x] Ingest normalized CI, dependency, docs, schema, evaluation, and release signals.
- [x] Redact secret assignments.
- [x] Deduplicate with stable fingerprints.
- [x] Support suppression with expiry.
- [x] Enforce an issue budget.
- [x] Keep branch and PR preparation disabled.

## Real consumer proof

The immutable registry in `consumers/registry.yaml` records:

- `fatmambot33/PermutiveAPI` — full platform;
- `fatmambot33/MatplotLibAPI` — full platform;
- `fatmambot33/openai-sdk-helpers` — agent tool.

Each repository passes its native test matrix, the canonical contract and evidence validator, and a
CodeQL analysis with retained SARIF. No repository-specific conformance exception is used.

## `v1.0.0` readiness criteria

- [x] Three materially different real repositories consume the standard.
- [x] The selected immutable vendored-contract distribution works outside this repository.
- [x] Release gates provide an equivalent control where private branch rulesets are plan-limited.
- [x] GitHub code-scanning alerts or reviewed retained SARIF are available for every registered consumer.
- [x] No repository-specific conformance exception is required.
- [ ] Accumulate compatibility evidence across multiple v0.x releases before declaring the contract stable.
