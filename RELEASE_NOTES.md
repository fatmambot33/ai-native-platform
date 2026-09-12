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


## AI-review governance opt-in

Repositories may opt into `evidence.paths.ai_review_workflow` to make current-HEAD Codex review part of merge governance. The declared workflow must pin the reusable gate to an immutable trusted framework commit, use a protected `pull_request_target` request path plus a read-only `pull_request`/review-dismissal wait path, and preserve the required `codex-review` check name.

Adoption is a one-time bootstrap: land the governed workflow and CODEOWNERS rules, then require `codex-review`, enable **Require review from Code Owners**, enable dismissal of stale approvals on new pushes (or equivalent latest-push approval protection), and keep conversation resolution required. Automated clean-reaction requests are bound to server-verified GitHub Actions run provenance for the exact PR and HEAD; the privileged maintainer bootstrap fallback exists only before the trusted request workflow is present on the default branch.
