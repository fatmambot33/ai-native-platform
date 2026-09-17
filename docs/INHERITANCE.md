# AI Native Inheritance Contract

**Contract version:** 1

AI Native inheritance lets a derived repository consume shared platform behavior without copying it. The declaration is repository-owned configuration; platform and profile capabilities remain platform-owned. Resolution is deterministic and provenance is part of the result.

## Derived repository declaration

A derived repository declares `.ai-native/derived.yaml`:

```yaml
version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: v0.3.0
profile: python-library
capabilities:
  welcome: inherit
  troubleshooting: inherit
  update: inherit
  doctor: inherit
extensions:
  welcome: []
  troubleshooting: []
ownership:
  local: []
```

`platform.repository` identifies the contract provider. `platform.ref` MUST be an immutable semantic version or 40-character commit SHA. `profile` is optional; when present it names exactly one platform-defined profile. Unknown contract versions, profiles, capabilities, modes, or ownership declarations fail closed.

## Resolution order

Resolution is ordered and deterministic:

1. platform capability;
2. selected profile contribution;
3. repository declaration;
4. repository-local extensions;
5. explicit repository override.

Every resolved capability records its contributing layers in that order. Consumers MUST be able to inspect this provenance; a repository-local value may not silently masquerade as inherited platform behavior.

## Capability composition

The v1 modes are:

- `inherit`: consume the value produced by the preceding platform/profile layers;
- `append`: preserve inherited behavior and append repository-local extensions;
- `override`: replace inherited behavior explicitly and record repository provenance;
- `disable`: intentionally remove the capability from the resolved repository contract.

A mode that requires repository content (`append` or `override`) is invalid without the corresponding local extension/value. `disable` cannot carry an extension. Conflicting declarations fail closed rather than selecting an arbitrary winner.

The initial inherited capability kernel is `welcome`, `troubleshooting`, `update`, and `doctor`. `welcome` and `troubleshooting` remain deterministic capabilities: skills or agent prompts may orchestrate them, but the reusable behavior and validation contract are not embedded only in a prompt.

## Profile contract

Profiles are platform-owned overlays. Phase 1 defines one evidence-backed skeleton, `python-library`, because the registered consumers are Python packages and the platform already validates Python library/CLI surfaces. A profile may add defaults or requirements but cannot weaken platform invariants. Repository declarations cannot redefine a profile.

## Ownership

Artifact ownership is declared now so the Phase 2 update engine can enforce it later:

- `inherited`: materialized entirely from platform/profile state and safe to replace with the compatible inherited version;
- `managed`: platform-managed artifact with explicit repository inputs;
- `merged`: platform-owned structure containing repository-owned extension regions;
- `local`: repository-owned artifact that platform update MUST NOT overwrite.

Phase 1 defines and validates ownership metadata only. It does not implement filesystem mutation or destructive update behavior.

## Doctor requirements

A derived repository is compliant only when deterministic validation proves that:

- the declaration matches the versioned schema;
- the platform reference is immutable;
- the selected profile exists;
- capability modes compose without conflicts;
- required inherited capabilities resolve;
- ownership paths are repository-relative, non-overlapping where ownership would be ambiguous, and do not escape the repository;
- resolved provenance is stable for identical inputs.

`doctor` must report declaration/resolution failures as deterministic findings. It must not repair, migrate, or overwrite repository content in Phase 1.

## Compatibility

Contract version 1 is additive to the existing AI Native product-manifest contract. Existing repositories that do not declare `.ai-native/derived.yaml` retain their current behavior. Opting into inheritance is explicit. Future incompatible inheritance changes require a new contract version; a validator MUST reject a newer unsupported version rather than guessing compatibility.
