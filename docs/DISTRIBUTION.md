# Private distribution

The supported `v0.1.0` distribution mode is private.

Consumer repositories require read access to this repository and a fine-grained read-only token
stored as `AI_NATIVE_PLATFORM_TOKEN`. The token must never be committed, echoed, or passed to
untrusted pull-request code.

Repository Actions access must explicitly permit the consumer repository. Consumers pin `v0.1.0`
or an immutable commit SHA.

Rollback consists of pinning the last trusted release. Revocation consists of deleting or rotating
the consumer token and removing the consumer from repository Actions access.
