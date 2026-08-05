# AI Native Platform

Canonical, self-hosting standard for first-class AI-native products.

This repository defines the contract that product repositories consume. It standardizes plugin packaging, local credential handling, agent interfaces, quality gates, GitHub issue-driven self-improvement, and governance.

## Core principles

- Plugin-first and agent-discoverable
- Local credentials only
- Typed, structured, deterministic interfaces
- GitHub Issues as the improvement work queue
- Agents may discover, plan, implement, test, and open pull requests
- Human approval remains mandatory for breaking, security, credential, public API, and release-impacting changes
- Every requirement is machine-validatable

## Consumer setup

A product repository keeps a local `AI_NATIVE_PLATFORM.yaml` that references this standard and declares product-specific capabilities.

```yaml
version: 1
standard:
  repository: fatmambot33/ai-native-platform
  ref: v1
product:
  name: example-product
```

Validate locally:

```bash
python -m pip install pyyaml jsonschema
python validator/validate.py AI_NATIVE_PLATFORM.yaml
```

Use the reusable GitHub Actions workflow:

```yaml
jobs:
  ai-native-platform:
    uses: fatmambot33/ai-native-platform/.github/workflows/validate.yml@v1
```

## Repository contents

- `standard/AI_NATIVE_PLATFORM.yaml`: canonical requirements
- `schemas/ai-native-platform.schema.json`: machine-readable schema
- `validator/validate.py`: semantic validator
- `.github/workflows/validate.yml`: reusable CI gate
- `.github/workflows/self-improve.yml`: self-hosting improvement discovery
- `templates/`: issue, manifest, and workflow templates
- `docs/GOVERNANCE.md`: automation and approval policy

## Versioning

The standard follows semantic versioning. Consumers should pin a release tag or immutable commit. Breaking contract changes require a major version.
