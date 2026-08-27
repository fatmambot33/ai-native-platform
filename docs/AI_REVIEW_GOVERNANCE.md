# AI Review Governance

AI review is a merge governance control for AI-native repositories, not a post-merge advisory step.

## Required invariant

A protected pull request must not merge until all of the following are true:

1. The repository's normal CI, validation, and security gates pass.
2. Codex has completed a review of the pull request's current HEAD commit.
3. Every actionable inline review thread is resolved.
4. Any new commit invalidates the previous AI review and triggers a review of the new HEAD.

Human approval is not required solely to satisfy this invariant. Repositories may separately require human decisions for changes covered by their governance policy.

## Reference implementation

Use `actions/codex-review-gate` from an immutable AI Native Platform commit or release. The action supports two phases:

- `request-only: "true"` requests `@codex review` immediately so Codex can work while CI runs.
- A second invocation without `request-only` waits until the current HEAD has a commit-matched Codex review or Codex's clean-review reaction.

The action never treats an older review as sufficient for a newer HEAD.

## GitHub protection

The protected branch should require the validation job that invokes the action and should enable **Require conversation resolution before merging**. For a solo maintainer, the required approving-review count can remain zero.

The action needs the workflow job to grant:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: read
```

`issues: write` is used only to create the HEAD-scoped `@codex review` request. Review and reaction state are read from GitHub.

## Codex setup

Codex must be configured for the repository in ChatGPT Codex Cloud. If the repository has no Codex environment, the gate intentionally cannot become green; configure the environment before making the gate a required merge condition.

## Auto-merge

Auto-merge is compatible with this model and is recommended for solo-maintainer repositories. Once CI, the current-HEAD AI review, and thread resolution are all green, GitHub may merge automatically.
