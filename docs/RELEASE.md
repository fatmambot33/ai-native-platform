# Release process

1. Merge a green release pull request into `main`.
2. The reusable consumer-conformance workflow validates every immutable entry in
   `consumers/registry.yaml`.
3. The release job verifies that `pyproject.toml`, the canonical standard, starter manifest,
   changelog, and release notes identify the same semantic version.
4. Ruff, tests, canonical validation, clean improvement discovery, package build, checksums, SPDX
   SBOM, and provenance generation must pass.
5. The workflow independently verifies every wheel and source archive against both `SHA256SUMS`
   and the SLSA-compatible `provenance.json` subject digests.
6. GitHub-hosted build attestations are additionally published when the repository visibility and
   account plan support the attestations API. User-owned private repositories currently do not.
7. If the semantic tag does not exist, the workflow creates one annotated tag at the verified
   `main` commit.
8. The workflow publishes an immutable GitHub prerelease and all verified assets, including
   checksums, SPDX SBOM, and provenance metadata.

The workflow is idempotent. If the release already exists, later `main` pushes do not move its tag
or replace its assets.

## Trust model

The release tag points to the GitHub-verified merge commit. Release artifacts carry SHA-256
checksums, an SPDX SBOM, and SLSA-compatible provenance whose subject digests are verified before
publication. GitHub-hosted attestations are an additional control when the platform supports them;
they are not required to make a user-owned private release verifiable.

## Failure recovery

A failed release must not be repaired by moving the tag. If a tag was created but release
publication failed, repair the workflow through a reviewed pull request and rerun it against the
same verified commit. After a published release, fixes require a new semantic version.
