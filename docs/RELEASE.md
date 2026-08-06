# Release process

1. Merge a green release pull request.
2. Confirm `pyproject.toml`, the canonical standard, starter manifest, changelog, and release notes
   all identify the same semantic version.
3. Enable required branch checks and review repository permissions.
4. Create an immutable signed tag such as `v0.1.0`.
5. The release workflow runs Ruff, tests, canonical validation, package build, checksums, SPDX SBOM,
   and GitHub provenance attestation.
6. The workflow verifies the tag, then publishes all assets to a GitHub release.

A failed release must not be repaired by moving the tag. Delete the failed draft release, fix the
repository through a reviewed pull request, and publish a new semantic version.
