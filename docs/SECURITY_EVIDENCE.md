# Security evidence

AI Native Platform v0.2 uses the implementation-neutral `evidence.paths.security_evidence` key whenever `quality.security_scan: true`.

The evidence must be repository-local and must make the enforced security-scanning control reviewable. It does not have to be a GitHub Actions workflow.

## Supported evidence patterns

### Workflow-backed scanning

Point `security_evidence` directly to the workflow that runs the required scan:

```yaml
evidence:
  paths:
    security_evidence: .github/workflows/security.yml
```

### Native GitHub CodeQL or ruleset enforcement

When scanning is enforced by GitHub default setup, code-scanning rules, or a repository ruleset, keep a repository-local evidence document that records the enforced control and point the manifest to it:

```yaml
evidence:
  paths:
    security_evidence: .github/SECURITY_ENFORCEMENT.md
```

That document should identify the enforced scanner or ruleset and the policy it applies. A duplicate custom workflow is not required merely to satisfy AI Native Platform validation.

## v0.1 migration

This is an intentional breaking rename. Replace:

```yaml
security_workflow: <path>
```

with:

```yaml
security_evidence: <path>
```

There is no `security_workflow` compatibility alias in v0.2.
