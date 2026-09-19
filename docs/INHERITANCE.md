# AI Native Inheritance Contract

**Contract version:** 1

AI Native inheritance lets a derived repository consume shared platform behavior without copying it. The declaration is repository-owned configuration; platform and profile capabilities remain platform-owned. Resolution is deterministic and provenance is part of the result.

## Derived repository declaration

A derived repository declares `.ai-native/derived.yaml`:

```yaml
version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: b2793f9fae645df1bda7492da01627396fc5e29f
profile: library
capabilities:
  welcome: inherit
  troubleshooting: inherit
  update: inherit
  doctor: inherit
ownership:
  local: []
```

The example pins a commit that contains the inheritance contract; consumers should pin an immutable release containing the contract when one is available. `platform.repository` identifies the contract provider. `platform.ref` MUST be an immutable semantic version or 40-character commit SHA. `profile` is optional; when present it names exactly one profile registered by `standard/AI_NATIVE_PLATFORM.yaml`. Unknown contract versions, profiles, capabilities, modes, duplicate YAML keys, or ownership declarations fail closed.

## Resolution order

Resolution is ordered and deterministic:

1. platform capability;
2. selected profile contribution;
3. repository declaration;
4. repository-local extensions;
5. explicit repository override.

Every resolved capability records its contributing layers in that order. Consumers MUST be able to inspect this provenance; a repository-local value may not silently masquerade as inherited platform behavior.

## Capability composition

The v1 modes are `inherit`, `append`, `override`, and `disable`. `append` and `override` require corresponding repository-local content; `inherit` and `disable` cannot carry an extension. Empty extension arrays are invalid; omit an extension key when it has no local content. Conflicting declarations fail closed rather than selecting an arbitrary winner.

The initial inherited capability kernel is `welcome`, `troubleshooting`, `update`, and `doctor`. `welcome` and `troubleshooting` remain deterministic capabilities: skills or agent prompts may orchestrate them, but the reusable behavior and validation contract are not embedded only in a prompt.

## Profile contract

Profiles are platform-owned overlays and use the same names as the authoritative registry in `standard/AI_NATIVE_PLATFORM.yaml`. Phase 1 supports the registered `library` profile for Python package consumers. A profile may add defaults or requirements but cannot weaken platform invariants. Repository declarations cannot redefine a profile.

## Ownership

Artifact ownership is declared now so the Phase 2 update engine can enforce it later. The ownership classes are `inherited`, `managed`, `merged`, and `local`; local artifacts MUST NOT be overwritten by platform update.

Ownership paths are portable repository-relative POSIX paths. Absolute paths, traversal segments, NUL bytes, Windows drive paths, and backslash-separated Windows paths fail closed. Cross-owner paths are compared case-insensitively so declarations remain unambiguous on default Windows and macOS filesystems. Phase 1 defines and validates ownership metadata only; it does not implement filesystem mutation or destructive update behavior.

## Doctor requirements

A derived repository is compliant only when deterministic validation proves that the declaration matches the versioned schema, the platform reference is immutable, the selected profile exists, capability modes compose without conflicts, required inherited capabilities resolve, ownership is portable and unambiguous, and provenance is stable.

`ai-native doctor` reports declaration, filesystem metadata/read, schema, and resolution failures as deterministic findings, including malformed encoding, duplicate keys, corrupt inheritance schemas, and unreadable or broken-symlink declarations. It must not repair, migrate, or overwrite repository content in Phase 1.

## Distribution and compatibility

The Python distribution includes the inheritance validator under the project-specific `ai_native_platform` package and includes `ai-native-derived.schema.json`, so installed `ai-native doctor` has the same contract as a source checkout without co-owning a generic top-level package namespace. Contract version 1 is additive to the existing AI Native product-manifest contract. Existing repositories that do not declare `.ai-native/derived.yaml` retain their current behavior. Opting into inheritance is explicit. Future incompatible inheritance changes require a new contract version; a validator MUST reject a newer unsupported version rather than guessing compatibility.
