# AI Native Platform

A canonical, evidence-backed standard for building first-class AI-native products and repositories.

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

Every profile has a passing and focused failing manifest fixture under `fixtures/`.

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

The migration command never silently downgrades a future manifest version.

## Distribution

### Immutable vendored contract

This is the proven default. A consumer pins an immutable standard commit, vendors that commit's
schema, and validates its manifest and repository evidence locally. The standard repository keeps an
immutable registry and continuously revalidates every registered consumer.

### Private reusable workflow

Repositories with private Actions access may call the reusable workflow using a fine-grained
read-only token stored as `AI_NATIVE_PLATFORM_TOKEN`:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.1.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
    secrets:
      standard_token: ${{ secrets.AI_NATIVE_PLATFORM_TOKEN }}
```

Never use `@main` in a production consumer. See `docs/DISTRIBUTION.md`.

## Real consumers

`consumers/registry.yaml` pins and continuously validates:

- `fatmambot33/PermutiveAPI` — full platform;
- `fatmambot33/MatplotLibAPI` — full platform;
- `fatmambot33/openai-sdk-helpers` — agent tool.

Every registered commit passes the canonical contract without repository-specific exceptions, its
native repository CI, and CodeQL analysis with retained SARIF.

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
- provenance metadata and GitHub build attestations.

The idempotent release workflow creates the immutable semantic tag and GitHub prerelease only after
those gates pass. Later `main` changes cannot move the tag or replace release assets. See
`docs/RELEASE.md`.

## Repository-plan control

GitHub reports that protected-branch rulesets are unavailable for this private repository on the
current plan. The v0.1 release workflow therefore duplicates and records all required release checks
as an equivalent control. If the repository becomes public or the plan changes, required-check
branch protection should be enabled as an additional control.

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
