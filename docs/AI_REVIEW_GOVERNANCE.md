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

The reference `.github/workflows/codex-review.yml` deliberately separates review **requesting** from the required merge **check**.

The `pull_request_target` job is loaded from the protected base branch. It never checks out pull-request code and has the only write capability: `issues: write`, used to post the HEAD-scoped `@codex review` request.

The `pull_request` job is the required `codex-review` check. GitHub attaches it naturally to the pull request's current check set. It has read-only permissions and waits for Codex evidence for exactly `github.event.pull_request.head.sha` while ordinary CI runs in parallel.

Both jobs invoke `actions/codex-review-gate` from an immutable 40-character framework commit. PR-scoped concurrency cancels superseded request/wait runs after a new push.

The required result is therefore not a raw commit status created through `statuses: write` or `checks: write`; those write scopes are intentionally absent from the governance workflow.

## Governance-code protection

A required `pull_request` job is only trustworthy if a pull request cannot silently redefine the workflow that produces it. Repositories adopting this model must protect these governance surfaces with CODEOWNERS:

```text
/.github/workflows/** @OWNER
/.github/CODEOWNERS @OWNER
```

The framework repository additionally protects its reusable gate action:

```text
/actions/codex-review-gate/** @OWNER
```

Enable **Require review from Code Owners** in the protected-main pull-request rule. The CODEOWNERS patterns are intentionally narrow, so ordinary source, documentation, and test changes still require zero human approvals. Governance/workflow changes are exceptional and require code-owner review or an explicitly authorized repository-owner bypass.

## Reference action

`actions/codex-review-gate` accepts only the real Codex connector identities, rejects dismissed reviews, matches submitted reviews by the full GitHub review `commit_id`, paginates GitHub API reads, and never treats an older review as sufficient for a newer HEAD.

A clean reaction is accepted only on the HEAD-specific request created by the trusted request job. The request must still be unedited (`created_at == updated_at`), so a stale Codex reaction cannot be carried forward by rewriting an older GitHub Actions comment. Editable maintainer comments are not accepted as clean-review evidence.

## GitHub protection

The protected branch should require the repository's normal CI/validation checks plus the `codex-review` job, and should enable **Require conversation resolution before merging** and **Require review from Code Owners**.

For a solo maintainer, the general required approving-review count can remain zero. Code-owner review applies only when one of the narrowly protected governance files changes.

The governance workflow permissions are intentionally split:

```yaml
# default and required PR job
permissions:
  contents: read

# trusted pull_request_target request job only
permissions:
  contents: read
  issues: write
  pull-requests: read
```

The required `codex-review` PR job additionally reads issue/review state but has no write scope.

## Evidence contract

`evidence.paths.ai_review_workflow` is opt-in for version-one manifests. Existing v1 manifests do not become invalid merely because they predate this governance feature.

When a repository declares `ai_review_workflow`, conformance validation verifies that it points to a real `.github/workflows/*.yml` or `.yaml` file with both event paths, immutable canonical action pins, request/wait separation, PR-scoped cancellation, and no writable status/check API.

## Bootstrap rule

A repository cannot enforce a newly added governance workflow or CODEOWNERS rule on the same pull request that introduces them. The first adoption PR is therefore a one-time bootstrap: it must receive an explicit current-HEAD Codex review and satisfy the repository's existing CI and governance before merge.

Immediately after that merge:

1. add `codex-review` to required status checks;
2. enable **Require review from Code Owners**;
3. keep **Require conversation resolution before merging** enabled.

Every later ordinary PR then follows the automated current-HEAD review gate. Governance-file changes remain intentionally exceptional.

## Codex setup

Codex must be configured for the repository in ChatGPT Codex Cloud. If the repository has no Codex environment, the required gate cannot become green; configure the environment before making `codex-review` required.

## Auto-merge

Auto-merge is compatible with this model and is recommended once the ruleset is active. GitHub may merge automatically after normal CI, the current-HEAD `codex-review` job, and review-thread resolution are all green.
