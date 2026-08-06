# Release process

1. Merge a green release pull request into `main`.
2. The reusable consumer-conformance workflow validates every immutable entry in
   `consumers/registry.yaml`.
3. The release job verifies that `pyproject.toml`, the canonical standard, starter manifest,
   changelog, and release notes identify the same semantic version.
4. Ruff, tests, canonical validation, clean improvement discovery, package build, checksums, SPDX
   SBOM, and provenance generation must pass.
5. GitHub creates build-provenance attestations for the release artifacts.
6. If the semantic tag does not exist, the workflow creates one annotated tag at the verified
   `main` commit.
7. The workflow publishes an immutable GitHub prerelease and all verified assets.

The workflow is idempotent. If the release already exists, later `main` pushes do not move its tag
or replace its assets.

## Trust model

The release tag points to the GitHub-verified merge commit. Release artifacts additionally carry
SHA-256 checksums, SPDX SBOM, provenance metadata, and GitHub build attestations. This is the v0.1
trust control in place of a locally configured long-lived tag-signing key.

## Failure recovery

A failed release must not be repaired by moving the tag. If a tag was created but release
publication failed, repair the workflow through a reviewed pull request and rerun it against the
same verified commit. After a published release, fixes require a new semantic version.
