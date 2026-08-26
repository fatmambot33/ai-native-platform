# AI Native Platform v0.2.0

A focused prerelease that makes security evidence implementation-neutral.

Highlights:

- `evidence.paths.security_evidence` is now the canonical evidence key when `quality.security_scan: true`;
- the v0.1 `security_workflow` key is intentionally removed with no compatibility alias;
- native GitHub CodeQL, default setup, and repository-ruleset enforcement can be proven by a repository-local evidence document without a duplicate custom workflow;
- workflow-backed security scanning remains fully supported by pointing `security_evidence` at the workflow;
- starter manifest, schema, fixtures, validator tests, documentation, and registered consumers migrate together;
- regression coverage verifies both workflow-backed and native-ruleset evidence paths.

Migration: rename `security_workflow` to `security_evidence`, preserve or replace the evidence path as appropriate, and pin the v0.2 contract.
