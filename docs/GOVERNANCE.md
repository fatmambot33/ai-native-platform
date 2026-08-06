# Governance

## Purpose

The standard should continuously improve while remaining predictable, reviewable, and safe.

## Autonomous scope

Agents may automatically:

- inspect code, tests, documentation, dependencies, CI failures, and conformance findings;
- create deduplicated GitHub issues with evidence and objective acceptance criteria;
- prioritize safe maintenance work;
- implement changes on isolated branches;
- add tests, documentation, examples, changelog entries, and roadmap updates;
- open pull requests and run all required checks.

## Human approval gates

Human approval is mandatory before merge for:

- breaking changes;
- security-sensitive behavior;
- credential collection, storage, transmission, or permissions;
- public API changes;
- release, publishing, or versioning changes;
- changes that expand network, filesystem, data, or write permissions.

## Safe auto-merge scope

Repositories may enable auto-merge for documentation, tests, formatting, examples, and non-breaking maintenance only when:

- an evidence-backed issue is linked;
- acceptance criteria are complete;
- all required checks pass;
- no protected path or high-impact classification is present;
- backward compatibility is preserved;
- the platform validator passes.

## Auditability

Every autonomous change must leave this chain:

`evidence -> issue -> branch -> pull request -> CI -> merge decision -> changelog`

Agents must not silently modify default branches, bypass checks, weaken governance, expose secrets, or approve their own high-impact changes.

## Standard changes

Changes to the JSON Schema, semantic rules, profiles, evidence model, release gates, or reusable workflow are public-contract changes. They require compatibility analysis, tests, migration notes, and human approval.
