# AI Native Platform

An Apache-2.0, evidence-backed standard for building first-class AI-native products and repositories.

The repository provides:

1. a versioned product-manifest contract;
2. profile-aware conformance rules;
3. an installable CLI and reusable CI gate;
4. first-class agent onboarding and deterministic recovery contracts;
5. governed, evidence-driven continuous improvement;
6. reproducible release metadata, SBOM, provenance, and real-consumer verification.

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

## Agent skills

Manifest v2 makes two agent-facing capabilities part of the AI-native contract:

- `agent.skills.welcome: true` — a deterministic first-use/readiness path that gets a user from installation to a verified usable state without exposing secrets;
- `agent.skills.troubleshooting: true` — a deterministic diagnostic/recovery path that routes structured failures to safe, actionable remediation.

The contract is implementation-neutral. Products exposing a plugin or MCP agent surface must provide
`evidence.paths.welcome_skill` and `evidence.paths.troubleshooting_skill`, but those paths may point to
packaged skill files, commands, playbooks, or equivalent deterministic repository-backed behavior.
Manifest-v1 consumers remain valid until they opt into v2.

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e '.[dev]'
```

The optional LLM self-improvement integration is kept out of the core dependency set:

```bash
python -m pip install -e '.[llm]'
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

Upgrade a legacy manifest:

```bash
ai-native upgrade AI_NATIVE_PLATFORM.yaml --dry-run
ai-native upgrade AI_NATIVE_PLATFORM.yaml --diff
ai-native upgrade AI_NATIVE_PLATFORM.yaml
```

The migration command never silently downgrades a future manifest version. For v0.3 it migrates
manifest v1 to v2, adds the welcome/troubleshooting skill declarations and conventional evidence
paths, updates v0.1/v0.2 release pins, and still rewrites the removed `security_workflow` evidence key
to `security_evidence`. Agent-surface repositories must create or replace the migrated skill evidence
paths before validation.

## Distribution

### Reusable public workflow

Public consumers can call the canonical workflow directly with no cross-repository secret:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.3.0
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
native repository CI, and CodeQL analysis. Their pinned manifest-v1 contracts remain valid while v2
is adopted explicitly.

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

### Optional LLM analysis

LLM analysis is an enhancement to deterministic discovery, not a requirement. By default, scheduled
runs make no model calls and incur no LLM API cost. A manual `workflow_dispatch` run must explicitly
set `use_ai: true`. Scheduled AI analysis activates only when the repository variable
`AI_NATIVE_LLM_ENABLED` is exactly `true`.

The current adapter uses OpenAI's Responses API with strict structured output. Configure the paid path
with the `OPENAI_API_KEY` Actions secret. The secret is exposed only to the model-analysis step and is
never passed to issue creation or deterministic validation. If the key is absent or the model call
fails, the workflow keeps the deterministic findings and completes without the AI enhancement.

Cost and quality controls are bounded and configurable with repository variables:

| Variable | Default | Purpose |
|---|---:|---|
| `AI_NATIVE_LLM_MODEL` | `gpt-5.6-luna` | Model used for optional analysis |
| `AI_NATIVE_LLM_MIN_CONFIDENCE` | `0.80` | Minimum accepted model confidence |
| `AI_NATIVE_LLM_MAX_INPUT_CHARS` | `50000` | Maximum repository text sent per run |
| `AI_NATIVE_LLM_MAX_OUTPUT_TOKENS` | `2000` | Maximum output tokens for the single model call |

The model receives a sanitized, bounded set of high-signal repository files plus current deterministic
findings. It has no GitHub credential or write capability. Model proposals must cite supplied evidence
paths, survive local path and confidence checks, avoid duplicates, and fit inside the same total issue
budget as deterministic findings before the workflow can create an issue.

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
- `tools/improvement_engine.py` — bounded deterministic discovery
- `tools/llm_improvement.py` — optional read-only LLM analysis and proposal validation
- `tools/release_artifacts.py` — checksums, SBOM, and provenance metadata
- `templates/` — starter manifest, workflow, and agent instructions
- `ROADMAP.md` — execution status and stability criteria
- `docs/GOVERNANCE.md` — autonomy and approval policy

## License

AI Native Platform is licensed under the Apache License 2.0. See `LICENSE`.
