# AI Native Platform

An Apache-2.0, evidence-backed standard for building first-class AI-native products and repositories.

The repository provides:

1. a versioned product-manifest contract;
2. profile-aware conformance rules;
3. an installable CLI and reusable CI gate;
4. governed, evidence-driven continuous improvement;
5. current-HEAD AI review governance for protected pull requests;
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

Public consumers can call the latest released canonical workflow directly with no cross-repository secret:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.2.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
```

Pin an exact release or immutable commit SHA. Never use `@main` in a production consumer. Unreleased
framework capabilities, including current-HEAD AI review governance, should be pinned to an immutable
commit until they are included in the next release.

### Immutable vendored contract

Consumers that prefer no remote workflow dependency can pin an immutable standard commit, vendor
that commit's schema, and validate their manifest and repository evidence locally. The standard
repository keeps an immutable registry and continuously revalidates every registered consumer.

Private mirrors may pass the reusable workflow's optional `standard_token` when cross-repository read
access requires authentication. See `docs/DISTRIBUTION.md`.

## AI review governance

The current unreleased framework adds AI review as a pre-merge governance control. A protected pull
request is eligible to merge only when normal CI and security gates pass, Codex has reviewed the
current HEAD commit, and all actionable review threads are resolved. A new commit invalidates the
older review evidence.

The reference `.github/workflows/codex-review.yml` uses two event paths. A base-trusted
`pull_request_target` job only creates the HEAD-scoped `@codex review` request. The required
`pull_request` job named `codex-review` is attached naturally to the PR check set, has read-only
permissions, and waits for current-HEAD evidence while ordinary CI runs in parallel. Both jobs invoke
the reusable gate from an immutable 40-character framework commit. The required result is not
published through writable commit-status or check APIs.

The workflow definitions and CODEOWNERS file are themselves narrowly CODEOWNERS-protected. Enable
**Require review from Code Owners** after bootstrap. Ordinary source, documentation, and test PRs can
still keep the general required human approval count at zero; only governance/workflow changes require
code-owner review or an explicitly authorized owner bypass.

Declaring `evidence.paths.ai_review_workflow` is opt-in for version-one manifests. If declared,
`ai-native validate` checks that the evidence is a real `.github/workflows` YAML file with the
canonical two-event request/wait semantics, immutable action pins, PR-scoped cancellation, and no
`statuses: write` or `checks: write` trust boundary.

Explicit re-review requires a Codex environment for the repository. The first PR that introduces the
governance workflow and narrow CODEOWNERS rules is a one-time bootstrap. After that PR receives a
current-HEAD Codex review and merges, add `codex-review` to the branch ruleset and enable code-owner
review. See `docs/AI_REVIEW_GOVERNANCE.md` for the full trust model and bootstrap rule.

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

Public operation requires protected `main`, required quality and conformance checks, published CodeQL
results, current-HEAD AI review where enabled, review-thread resolution, and code-owner protection of
the governance workflow surfaces. The workflows remain safe to execute while the repository is
private: CodeQL retains SARIF without uploading it and release provenance remains independently
verifiable. Once public, CodeQL publication and GitHub-hosted build attestations activate automatically.

## Repository structure

- `schemas/ai-native-platform.schema.json` — product contract
- `standard/AI_NATIVE_PLATFORM.yaml` — standard identity and release gates
- `actions/codex-review-gate/` — reusable current-HEAD Codex merge gate
- `.github/workflows/codex-review.yml` — split trusted-request/read-only-required AI-review governance
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
