# AI Native Platform v0.3.0

A prerelease that makes deterministic onboarding and recovery first-class AI-native contract capabilities while preserving manifest-v1 compatibility.

Highlights:

- manifest v2 adds `agent.skills.welcome: true` and `agent.skills.troubleshooting: true`;
- products exposing `interfaces.plugin: true` or `interfaces.mcp: true` must provide repository evidence for both skills;
- evidence is implementation-neutral: packaged skill files, commands, playbooks, or equivalent deterministic repository-backed behavior are valid;
- the canonical starter paths are `skills/welcome/SKILL.md` and `skills/troubleshooting/SKILL.md`;
- existing manifest-v1 consumers continue to validate without the new fields;
- `ai-native upgrade` deterministically migrates v1 manifests to v2 and updates the standard ref to v0.3.0;
- the checklist now treats guided onboarding and deterministic recovery as first-class agent-readiness requirements;
- the product-roadmap and optional read-only LLM improvement features introduced since v0.2 are included in the same prerelease train.

Migration: run `ai-native upgrade AI_NATIVE_PLATFORM.yaml --diff`, implement or point `welcome_skill` and `troubleshooting_skill` evidence at real repository behavior for plugin/MCP products, validate locally, and then pin the immutable v0.3 contract.

## Unreleased inheritance preview

The current development branch adds an opt-in inheritance contract for derived repositories. It is not part of v0.3.0. A derived repository can start from `templates/derived.yaml`, install it as `.ai-native/derived.yaml`, keep the starter's registered `platform.ref` (`3e49406e8ac3a9c1f28c6f91b9356ff24a5f41cc`) until another contract-v1 provider revision is explicitly registered, and run `ai-native doctor`. The declaration composes the `welcome`, `troubleshooting`, `update`, and `doctor` capabilities and records portable artifact ownership for later managed updates. Repositories that do not add the declaration keep their existing behavior.

Until a release containing contract v1 is registered, consumers must use the registered implementation checkpoint in the starter rather than v0.3.0 or an arbitrary commit SHA; `ai-native doctor` rejects unregistered refs. The normative rules remain in `docs/INHERITANCE.md` and migration details are tracked in `CHANGELOG.md` under Unreleased.

## Unreleased AI-review governance preview

AI-review governance is not part of the v0.3.0 contract. The current development branch adds an opt-in `evidence.paths.ai_review_workflow` capability for a future release; consumers pinned to v0.3.0 must not rely on that validator behavior yet.

The unreleased design requires an immutable trusted gate revision, a protected `pull_request_target` request path, a read-only `pull_request`/review-dismissal wait path, the stable `codex-review` check name, CODEOWNERS protection, stale-approval invalidation, and an up-to-date protected branch before merge. Adoption and migration guidance remains in `CHANGELOG.md` under Unreleased and `docs/AI_REVIEW_GOVERNANCE.md` until a new version ships.