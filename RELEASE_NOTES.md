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
