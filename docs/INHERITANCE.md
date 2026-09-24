# AI Native Inheritance Contract

**Contract version:** 1

AI Native inheritance lets a derived repository consume shared platform behavior without copying it. The declaration is repository-owned configuration; platform and profile capabilities remain platform-owned. Resolution is deterministic and provenance is part of the result.

## Derived repository declaration

A derived repository declares `.ai-native/derived.yaml`:

```yaml
version: 1
platform:
  repository: fatmambot33/ai-native-platform
  ref: 40e105f9c373e9588fbdd1c8130a8aba13f8671a
profile: library
capabilities:
  welcome: inherit
  troubleshooting: inherit
  update: inherit
  doctor: inherit
ownership:
  local: []
```

The platform reference MUST be immutable: either a full 40-character commit SHA or an exact semantic-version tag whose release contains inheritance contract version 1. Until such a release is published, use the immutable implementation checkpoint shown above. Branches, moving tags, and version ranges are invalid.

The declaration is optional. A repository without `.ai-native/derived.yaml` keeps the existing platform behavior and remains compatible with the pre-inheritance doctor path.

## Composition

The v1 capabilities are `welcome`, `troubleshooting`, `update`, and `doctor`. Every declaration selects exactly one composition mode for each capability:

- `inherit`: use platform/profile behavior unchanged.
- `append`: keep inherited behavior and add repository extensions.
- `override`: replace inherited behavior with repository extensions.
- `disable`: explicitly disable the capability for the repository.

`append` and `override` require non-empty local extensions. `inherit` and `disable` cannot carry local extensions. Resolution records provenance so consumers can distinguish inherited behavior from repository decisions.

## Ownership

Optional ownership classes are `inherited`, `managed`, `merged`, and `local`. Paths are repository-relative portable paths. Validation rejects absolute paths, traversal, Windows drive or device aliases, invalid Windows filename characters, NUL bytes, unsafe trailing characters, overlong components or complete paths, and Unicode/case aliases that overlap across ownership classes.

The declaration and its `.ai-native` directory must be repository-owned regular filesystem entries rather than symlinks. Doctor fails closed for malformed, unreadable, ambiguous, or unsafe opted-in declarations.

## Validation

Run:

```text
ai-native doctor --root .
```

The public doctor command runs the existing product checks and inheritance validation. A valid declaration must satisfy the packaged v1 JSON Schema and the cross-field safety invariants. A repository that has not opted in receives the normal compatibility behavior.

Canonical platform validation additionally checks the inheritance schema, starter declaration, packaged schema copy, documentation and governed executable surfaces together so distribution artifacts cannot silently drift from the source contract.
