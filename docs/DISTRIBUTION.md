# Distribution

`v0.2.0` supports two immutable distribution modes.

## Reusable public workflow

Public consumers can call the canonical workflow directly without a cross-repository secret:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.2.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
```

Consumers must pin `v0.2.0` or an immutable commit SHA. Never use `@main` in production.

The workflow accepts an optional `standard_token` only for private mirrors or other authenticated
cross-repository scenarios. Public consumption does not require it, and tokens must never be
committed, echoed, or exposed to untrusted pull-request code.

## Vendored contract snapshot

Consumers that prefer no remote workflow dependency can pin an immutable standard commit, vendor
that commit's JSON Schema, and run the repository-evidence validator in their own CI. The central
`consumers/registry.yaml` pins each registered consumer commit and continuously revalidates it with
the packaged `ai-native` CLI.

This mode requires no cross-repository secret.

## Rollback and revocation

Rollback consists of pinning the last trusted release or contract commit. For authenticated private
workflow access, revoke or rotate the token and remove repository Actions access. For vendored
contracts, revert the consumer pull request or pin the previous immutable schema snapshot.
