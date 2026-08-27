# AI Review Governance

AI review is a merge governance control for AI-native repositories, not a post-merge advisory step.

## Required invariant

A protected pull request must not merge until all of the following are true:

1. The repository's normal CI, validation, and security gates pass.
2. Codex has completed a review of the pull request's current HEAD commit.
3. Every actionable inline review thread is resolved.
4. Any new commit invalidates the previous AI review and triggers a review of the new HEAD.

Human approval is not required solely to satisfy this invariant. Repositories may separately require human decisions for changes covered by their governance policy.

## Trusted execution model

The merge gate must not execute from code controlled by the pull request it is judging. A PR can edit an ordinary `pull_request` workflow while preserving its required check name, so that workflow is not a sufficient security boundary for AI-review enforcement.

Use a dedicated `pull_request_target` workflow whose definition comes from the protected base branch. That workflow must check out only the base revision (never pull-request code) and invoke `actions/codex-review-gate` from trusted base-branch contents or an immutable AI Native Platform commit.

A `pull_request_target` workflow run is associated with the protected base revision, not the PR HEAD. The reference workflow therefore publishes an explicit `codex-review` commit status to `github.event.pull_request.head.sha`. That HEAD status—not the workflow job name—is the status check that branch rulesets require.

The reference workflow is `.github/workflows/codex-review.yml`. It starts as soon as a pull request is opened, synchronized, reopened, or marked ready, marks the current HEAD review pending, requests Codex, waits for current-HEAD evidence while ordinary PR CI runs in parallel, then publishes `codex-review` success or failure on that same HEAD. PR-scoped concurrency cancels superseded waits when a newer commit is pushed.

## Reference action

`actions/codex-review-gate` accepts only the real Codex connector identities, rejects dismissed reviews, binds clean-review reactions to a HEAD-specific request, paginates GitHub API reads, and never treats an older review as sufficient for a newer HEAD.

A valid request is authored by `github-actions[bot]`, starts with the exact `@codex review` command, and includes the full current-HEAD gate marker. The trusted workflow owns request creation, including for fork and Dependabot pull requests, so editable maintainer comments are not accepted as clean-review evidence.

## GitHub protection

The protected branch should require the repository's normal CI/validation checks plus the `codex-review` HEAD status, and should enable **Require conversation resolution before merging**. For a solo maintainer, the required approving-review count can remain zero.

The trusted workflow needs:

```yaml
permissions:
  contents: read
  issues: write
  pull-requests: read
  statuses: write
```

`issues: write` is used only to create the HEAD-scoped `@codex review` request. `statuses: write` publishes the `codex-review` pending/success/failure state on the PR HEAD. Review and reaction state are read from GitHub.

## Bootstrap rule

A repository cannot protect itself with a new `pull_request_target` workflow until that workflow exists on the protected base branch. The first adoption PR is therefore a one-time bootstrap: it must receive a current-HEAD Codex review and satisfy the repository's existing human-governance requirements before merge. Immediately after that merge, add the new `codex-review` status to the branch ruleset. Every later PR is then governed by base-branch code.

## Codex setup

Codex must be configured for the repository in ChatGPT Codex Cloud. If the repository has no Codex environment, the gate intentionally cannot become green; configure the environment before making the gate a required merge condition.

## Auto-merge

Auto-merge is compatible with this model and is recommended for solo-maintainer repositories. Once CI, current-HEAD AI review, and thread resolution are all green, GitHub may merge automatically.
