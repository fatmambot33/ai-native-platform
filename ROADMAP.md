# Roadmap

## Phase 0 — Truthful foundation

Status: **complete**

- [x] Correct repository metadata, issue forms, templates, and workflow naming.
- [x] Document immutable references and private-repository consumption.

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

Status: **repository implementation complete; administrative activation remains**

- [x] Choose private distribution.
- [x] Add a complete private consumer repository fixture.
- [x] Build wheel and source artifacts.
- [x] Generate checksums and SPDX SBOM.
- [x] Generate provenance inputs and GitHub build attestations.
- [x] Verify tag and package version alignment.
- [x] Publish immutable release assets from the tag workflow.
- [ ] Enable branch protection and require Quality, validation, and CodeQL.
- [ ] Enable GitHub code-scanning alert publication if supported by the repository plan.
- [ ] Provision the private consumer token and run the fixture from a separate repository.
- [ ] Create the immutable `v0.1.0` tag after the release PR merges.

## Phase 4 — Evidence-driven self-improvement

Status: **complete for read-only discovery and issue creation**

- [x] Detect canonical, fixture, and release drift.
- [x] Ingest normalized CI, dependency, docs, schema, evaluation, and release signals.
- [x] Redact secret assignments.
- [x] Deduplicate with stable fingerprints.
- [x] Support suppression with expiry.
- [x] Enforce an issue budget.
- [x] Keep branch and PR preparation disabled.

## `v1.0.0` exit criteria

- Three materially different real repositories consume the standard.
- Private workflow consumption is proven outside this repository.
- Branch protection and required checks are enabled.
- GitHub code-scanning alerts are published or an equivalent reviewed SARIF process is adopted.
- No repository-specific conformance exception is required.
