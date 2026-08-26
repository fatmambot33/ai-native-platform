# AI Native Platform

An Apache-2.0, evidence-backed standard for building first-class AI-native products and repositories.

The repository provides:

1. a versioned product-manifest contract;
2. profile-aware conformance rules;
3. an installable CLI and reusable CI gate;
4. governed, evidence-driven continuous improvement;
5. reproducible release metadata, SBOM, provenance, and real-consumer verification.

## Profiles

| Profile | Required surface |
|---|---|
| `library` | SDK and JSON Schema |
| `cli` | CLI and JSON Schema |
| `service` | JSON Schema plus OpenAPI or SDK |
| `agent-tool` | JSON Schema plus plugin or MCP |
| `plugin` | Plugin and JSON Schema |
| `full-platform` | SDK, CLI, plugin, and JSON Schema |

MCP is opt-in. Consumers without an MCP surface may omit `interfaces.mcp`; declaring `mcp: true`
requires repository evidence for that surface. Every profile has a passing and focused failing manifest
fixture under `fixtures/`.

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e '.[dev]'
```

## CLI

```bash
ai-native init
ai-native validate AI_NATIVE_PLATFORM.yaml
ai-native score AI_NATIVE_PLATFORM.yaml
ai-native doctor AI_NATIVE_PLATFORM.yaml
```

Machine-readable output:

```bash
ai-native validate AI_NATIVE_PLATFORM.yaml --format json
ai-native validate AI_NATIVE_PLATFORM.yaml --format sarif --output results.sarif
```

Upgrade a legacy or unversioned manifest:

```bash
ai-native upgrade AI_NATIVE_PLATFORM.yaml --dry-run
ai-native upgrade AI_NATIVE_PLATFORM.yaml --diff
ai-native upgrade AI_NATIVE_PLATFORM.yaml
```

The migration command never silently downgrades a future manifest version. For the v0.2 contract it
also rewrites the removed `security_workflow` evidence key to `security_evidence` and updates an old
v0.1 standard pin; the v0.2 validator itself does not accept the removed key.

## Distribution

### Reusable public workflow

Public consumers can call the canonical workflow directly with no cross-repository secret:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.2.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
```

Pin an exact release or immutable commit SHA. Never use `@main` in a production consumer.

### Immutable vendored contract

Consumers that prefer no remote workflow dependency can pin an immutable standard commit, vendor
that commit's schema, and validate their manifest and repository evidence locally. The standard
repository keeps an immutable registry and continuously revalidates every registered consumer.

Private mirrors may pass the reusable workflow's optional `standard_token` when cross-repository read
access requires authentication. See `docs/DISTRIBUTION.md`.

## Real consumers

`consumers/registry.yaml` pins and continuously validates:

- `fatmambot33/PermutiveAPI` — full platform;
- `fatmambot33/MatplotLibAPI` — full platform;
- `fatmambot33/openai-sdk-helpers` — agent tool.

Every registered commit passes the canonical contract without repository-specific exceptions, its
native repository CI, and CodeQL analysis.

## Evidence-driven self-improvement

The scheduled workflow:

- validates the canonical repository;
- detects fixture, consumer, and release drift;
- ingests normalized CI, dependency, documentation, schema, evaluation, and release signals;
- redacts common secret assignments;
- suppresses reviewed false positives;
- deduplicates by stable fingerprint;
- enforces a maximum issue budget;
- never prepares branches or pull requests without separate governance approval.

External normalized signals belong in `.ai-native/signals.json`. See
`.ai-native/signals.example.json`.

## Release integrity

A verified `main` run must pass:

- all registered consumer validations;
- Ruff, tests, and canonical validation;
- clean evidence-driven discovery;
- wheel and source builds;
- SHA-256 checksum verification;
- SPDX 2.3 SBOM generation;
- SLSA-compatible provenance subject verification.

The idempotent release workflow creates the immutable semantic tag and GitHub prerelease only after
those gates pass. Checksums, SBOM, and provenance are published with the artifacts. GitHub-hosted
attestations are added automatically when repository visibility and account capabilities support
them. Later `main` changes cannot move the tag or replace release assets. See `docs/RELEASE.md`.

## Public repository controls

Public operation requires protected `main`, required quality and conformance checks, and published
CodeQL results. The workflows remain safe to execute while the repository is private: CodeQL retains
SARIF without uploading it and release provenance remains independently verifiable. Once public,
CodeQL publication and GitHub-hosted build attestations activate automatically.

## Repository structure

- `schemas/ai-native-platform.schema.json` — product contract
- `standard/AI_NATIVE_PLATFORM.yaml` — standard identity and release gates
- `ai_native.py` — validator, migration library, SARIF, and CLI
- `fixtures/` — passing, failing, and consumer fixtures
- `consumers/registry.yaml` — immutable real-consumer proof
- `tools/improvement_engine.py` — bounded discovery
- `tools/release_artifacts.py` — checksums, SBOM, and provenance metadata
- `templates/` — starter manifest, workflow, and agent instructions
- `ROADMAP.md` — execution status and stability criteria
- `docs/GOVERNANCE.md` — autonomy and approval policy

## License

AI Native Platform is licensed under the Apache License 2.0. See `LICENSE`.
