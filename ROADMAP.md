# Roadmap

The standard advances only when the previous phase has objective evidence.

## Phase 0 — Truthful foundation

Status: **implemented in the v0.1 roadmap pull request**

- [x] Fix issue-form syntax and label assumptions.
- [x] Align self-improvement workflow naming.
- [x] Add the advertised templates.
- [x] Document private-repository consumption.
- [x] Replace floating production references with exact-version guidance.

## Phase 1 — Authoritative contract

Status: **implemented in the v0.1 roadmap pull request**

- [x] Enforce JSON Schema draft 2020-12.
- [x] Reject unknown controlled fields.
- [x] Add explicit extension namespace.
- [x] Add product profiles and conditional interface rules.
- [x] Replace broad filesystem heuristics with declared repository evidence.
- [x] Keep semantic validation for cross-field rules that JSON Schema cannot express clearly.

## Phase 2 — Conformance product

Status: **core implemented; advanced reporting remains**

- [x] Package an installable CLI.
- [x] Add `init`, `validate`, `score`, and `doctor`.
- [x] Add JSON output.
- [x] Add unit and repository-evidence tests.
- [ ] Add SARIF output and GitHub code-scanning annotations.
- [ ] Add migration automation between manifest versions.
- [ ] Add consumer fixture repositories for every profile.

## Phase 3 — Trustworthy release

Status: **foundation implemented; release intentionally gated**

- [x] Add changelog, roadmap, security policy, contribution guide, agent instructions, and PR template.
- [x] Add quality, CodeQL, and dependency-update workflows.
- [x] Retain CodeQL SARIF artifacts while repository code scanning is unavailable.
- [x] Add package build smoke tests.
- [ ] Decide public versus private distribution.
- [ ] Enable repository code scanning and publish SARIF findings.
- [ ] Configure branch protection and required checks.
- [ ] Prove private and public consumer workflows.
- [ ] Publish signed `v0.1.0` release.
- [ ] Add provenance attestations and SBOM.

## Phase 4 — Evidence-driven self-improvement

Status: **baseline implemented**

- [x] Produce structured canonical findings.
- [x] Create one deduplicated issue per finding.
- [x] Preserve human approval gates.
- [ ] Ingest failed and flaky CI signals.
- [ ] Detect dependency, documentation, schema, evaluation, and release drift.
- [ ] Add governed safe-maintenance PR preparation.

## `v1.0.0` exit criteria

- At least three materially different repositories consume the standard.
- Every profile has a passing and failing fixture.
- The contract has migration tests and compatibility guarantees.
- The reusable workflow works with documented public and private distribution modes.
- Releases include changelog, SBOM, provenance, and signed immutable tags.
- No repository-specific exception is required to pass conformance.
