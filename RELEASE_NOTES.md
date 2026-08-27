# AI Native Platform v0.3.0

A prerelease focused on solo-maintainer merge governance: Codex review becomes a current-HEAD merge gate instead of a post-merge advisory signal.

Highlights:

- the canonical standard now requires current-HEAD AI review and review-thread resolution as release gates;
- `actions/codex-review-gate` provides the reusable Codex enforcement implementation;
- review requests start before validation so Codex latency overlaps ordinary CI work;
- a review is accepted only when its GitHub `commit_id` matches the current pull-request HEAD, with the reviewed-SHA body retained only as a compatibility fallback;
- clean reviews are accepted only from a reaction on the HEAD-specific `@codex review` request, preventing stale clean signals from authorizing a newer commit;
- all review, comment, and reaction reads paginate, and polling defaults to 60 seconds to bound API usage;
- read-only pull-request tokens fail safely: fork or Dependabot contexts can use a maintainer-posted exact `@codex review` command carrying the current short SHA on a later line;
- protected branches can keep zero required human approvals for ordinary solo-maintainer changes while still requiring normal CI/security gates and GitHub conversation resolution;
- permission-expanding, breaking, security, credential, public-API, and release changes remain subject to the framework's separate human-approval governance.

Migration: configure a Codex environment for each repository that will use explicit re-review, invoke the pinned `actions/codex-review-gate` action from an already-required validation job, grant that job `issues: write` and `pull-requests: read`, keep GitHub's review-thread resolution rule enabled, and pin the v0.3 framework release or its immutable commit.
