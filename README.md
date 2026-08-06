# AI Native Platform

A canonical, evidence-backed standard for building first-class AI-native products and repositories.

The repository provides:

1. a versioned product-manifest contract;
2. profile-aware conformance rules;
3. an installable CLI and reusable CI gate;
4. governed, evidence-driven continuous improvement;
5. reproducible release metadata, SBOM, and provenance.

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

## Private distribution

`v0.1.0` uses a **private distribution model**. Consumers must:

1. grant the consumer repository access to this private Actions workflow;
2. create a fine-grained token with read-only contents access to this repository;
3. store it as `AI_NATIVE_PLATFORM_TOKEN`;
4. pin the exact immutable release.

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.1.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
    secrets:
      standard_token: ${{ secrets.AI_NATIVE_PLATFORM_TOKEN }}
```

Never use `@main` in a production consumer. A complete consumer repository fixture is in
`fixtures/consumer-repository/`.

## Evidence-driven self-improvement

The scheduled workflow:

- validates the canonical repository;
- detects fixture and release drift;
- ingests normalized CI, dependency, documentation, schema, evaluation, and release signals;
- redacts common secret assignments;
- suppresses reviewed false positives;
- deduplicates by stable fingerprint;
- enforces a maximum issue budget;
- never prepares branches or pull requests without separate governance approval.

External normalized signals belong in `.ai-native/signals.json`. See
`.ai-native/signals.example.json`.

## Release integrity

The quality gate builds the package and verifies:

- wheel and source distribution;
- SHA-256 checksums;
- SPDX 2.3 SBOM;
- SLSA-compatible provenance statement inputs;
- clean wheel installation;
- SARIF output.

A `v*.*.*` tag additionally creates GitHub build-provenance attestations and publishes an
immutable GitHub release. See `docs/RELEASE.md`.

## Repository administration

The code defines the required checks: `Quality`, `Validate AI-native platform`, and `CodeQL`.
Repository administrators must enable branch protection with these checks and enable GitHub code
scanning if alert publication is desired. CodeQL analysis remains effective without alert
publication because SARIF is retained as an artifact.

## Repository structure

- `schemas/ai-native-platform.schema.json` — product contract
- `standard/AI_NATIVE_PLATFORM.yaml` — standard identity and release gates
- `ai_native.py` — validator, migration library, SARIF, and CLI
- `fixtures/` — passing, failing, and consumer repositories
- `tools/improvement_engine.py` — bounded discovery
- `tools/release_artifacts.py` — checksums, SBOM, and provenance metadata
- `templates/` — starter manifest, workflow, and agent instructions
- `ROADMAP.md` — execution and remaining administrative gates
- `docs/GOVERNANCE.md` — autonomy and approval policy
