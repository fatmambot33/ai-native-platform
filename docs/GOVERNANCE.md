# Governance

## Purpose

The platform should continuously improve itself while remaining predictable, reviewable, and safe.

## Autonomous scope

Agents may automatically:

- inspect code, tests, documentation, dependencies, TODO markers, and CI failures;
- create deduplicated GitHub issues with evidence and acceptance criteria;
- prioritize safe maintenance work;
- implement changes on isolated branches;
- add tests, documentation, examples, changelog entries, and roadmap updates;
- open pull requests and run all required checks.

## Human approval gates

A human approval is mandatory before merge for:

- breaking changes;
- security-sensitive behavior;
- credential collection, storage, transmission, or permissions;
- public API changes;
- release, publishing, or versioning changes;
- changes that expand network, filesystem, or write permissions.

## Safe auto-merge scope

Repositories may enable auto-merge for documentation, tests, formatting, examples, and non-breaking maintenance only when:

- the issue is linked;
- acceptance criteria are complete;
- all required checks pass;
- no protected path or high-impact label is present;
- the change preserves backward compatibility;
- the platform validator passes.

## Auditability

Every autonomous change must leave an auditable chain:

`evidence -> issue -> branch -> pull request -> CI -> merge decision -> changelog`

Agents must not silently modify default branches, bypass checks, weaken governance, expose secrets, or approve their own high-impact changes.
