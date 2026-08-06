# Distribution

`v0.1.0` supports two immutable distribution modes.

## Vendored contract snapshot

This is the proven mode used by the registered real consumers. A consumer pins an immutable
standard commit, vendors that commit's JSON Schema, and runs the repository-evidence validator in
its own CI. The central `consumers/registry.yaml` pins each consumer commit and continuously
revalidates it with the packaged `ai-native` CLI.

This mode requires no cross-repository secret and works for public consumers while the standards
repository remains private.

## Private reusable workflow

Repositories granted private Actions access may instead call the reusable workflow and pass a
fine-grained read-only token stored as `AI_NATIVE_PLATFORM_TOKEN`. The token must never be committed,
echoed, or exposed to untrusted pull-request code.

Consumers must pin `v0.1.0` or an immutable commit SHA. Never use `@main` in production.

## Rollback and revocation

Rollback consists of pinning the last trusted release or contract commit. For private reusable
workflow access, revoke or rotate the token and remove repository Actions access. For vendored
contracts, revert the consumer pull request or pin the previous immutable schema snapshot.
