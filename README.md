# AI Native Platform

A canonical, evidence-backed standard for building first-class AI-native products and repositories.

The repository provides four things:

1. a versioned product manifest contract;
2. profile-aware conformance rules;
3. a reusable validator and CLI;
4. governed, issue-driven continuous improvement.

## Design principles

- **Schema first:** product declarations are validated with JSON Schema draft 2020-12.
- **Evidence backed:** every declared capability points to concrete repository evidence.
- **Profile aware:** libraries, CLIs, services, agent tools, plugins, and full platforms have different required surfaces.
- **Deterministic:** tools, inputs, outputs, errors, versions, and discovery remain machine-readable.
- **Safe by default:** credentials remain local and high-impact changes require human approval.
- **Single contract:** humans, CI, agents, SDKs, and plugins consume the same manifest.

## Profiles

Choose the smallest profile matching the product:

| Profile | Required surface |
|---|---|
| `library` | SDK and JSON Schema |
| `cli` | CLI and JSON Schema |
| `service` | JSON Schema plus OpenAPI or SDK |
| `agent-tool` | JSON Schema plus plugin or MCP |
| `plugin` | Plugin and JSON Schema |
| `full-platform` | SDK, CLI, plugin, and JSON Schema |

## Install

From a checkout:

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e '.[dev]'
```

## Quick start

Create a starter manifest:

```bash
ai-native init
```

Replace the example values and evidence paths, then validate:

```bash
ai-native validate AI_NATIVE_PLATFORM.yaml
ai-native score AI_NATIVE_PLATFORM.yaml
ai-native doctor AI_NATIVE_PLATFORM.yaml
```

Machine-readable output is available for validation and scoring:

```bash
ai-native validate AI_NATIVE_PLATFORM.yaml --json
```

## Reusable GitHub Actions workflow

After the first release, pin the exact release tag:

```yaml
jobs:
  conformance:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v0.1.0
    with:
      manifest: AI_NATIVE_PLATFORM.yaml
```

This repository is currently private. A consuming private repository may need to pass a fine-grained token that can read this repository:

```yaml
    secrets:
      standard_token: ${{ secrets.AI_NATIVE_PLATFORM_TOKEN }}
```

Never use `@main` in a production consumer. Pin an exact semantic release or immutable commit SHA.

## Security scanning

CodeQL runs on pull requests, pushes to `main`, and a weekly schedule. While GitHub code scanning is unavailable for this private repository, the workflow retains the generated SARIF as a 14-day workflow artifact instead of failing during upload. Enabling repository code scanning and publishing alerts is a release gate tracked separately.

## Repository structure

- `schemas/ai-native-platform.schema.json` — canonical product contract
- `standard/AI_NATIVE_PLATFORM.yaml` — standard identity, profiles, principles, and release gates
- `ai_native.py` — validator library and CLI
- `validator/` — compatibility entry points and canonical self-validation
- `templates/` — starter manifest, workflow, and agent instructions
- `CHECKLIST.md` — comprehensive target-state checklist
- `ROADMAP.md` — ordered execution plan and completion state
- `docs/GOVERNANCE.md` — autonomy and approval policy

## Release policy

The project follows semantic versioning. It remains prerelease until consumer fixtures prove that multiple repository profiles validate without repository-specific exceptions.

Breaking contract changes require a major version after `v1.0.0`. Before `v1`, every release must document migrations explicitly.
