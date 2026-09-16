# AI Native Plan Protocol

**Protocol version:** 1

The AI Native Plan protocol makes GitHub the persistent execution state for multi-step AI-native improvements. Durable architecture remains in repository documentation; executable state lives in GitHub issues and pull requests so a fresh agent can reconstruct and resume work without conversation history.

## Concepts

An **Idea** is candidate work and is not executable. A **Plan** is an executable objective with explicit preconditions, invariants, phases, and acceptance criteria. A **Phase** is the smallest independently resumable unit and normally produces one focused pull request or one verifiable non-code outcome. A **PR** is implementation evidence for one active Phase where practical.

## Plan contract

A Plan issue MUST contain these headings and values:

```text
## Plan
Protocol: 1
State: draft | ready | running | blocked | verifying | done

## Objective
...

## Preconditions
- [ ] ...

## Invariants
- ...

## Phases
- [ ] #<issue> — ...

## Acceptance criteria
- [ ] ...

## Execution policy
...
```

`Preconditions` are hard gates. An unchecked precondition prevents implementation. `Phases` MUST be ordered or carry explicit dependency metadata. `Acceptance criteria` describe independently observable outcomes and MUST NOT be inferred merely from merged PRs. Durable design documents SHOULD be linked from the Plan.

State semantics are deterministic:

- `draft`: contract is incomplete or not approved for execution.
- `ready`: contract is complete and all plan-level preconditions are satisfied.
- `running`: at least one Phase is active.
- `blocked`: no Phase may run because a hard precondition or dependency is unsatisfied.
- `verifying`: implementation phases are complete and Plan acceptance criteria are being independently checked.
- `done`: every acceptance criterion has been independently verified.

## Phase contract

A Phase issue MUST contain:

```text
Parent plan: #<issue>
State: ready | running | blocked | verifying | done
Blocked by: none | #<issue>[, #<issue> ...]
Linked PR: none | #<pr>

## Objective
...

## Scope
...

## Definition of done
- [ ] ...

## Deterministic validation
- ...
```

A Phase is runnable only when its parent Plan is `ready` or `running`, every plan-level precondition is satisfied, every issue in `Blocked by` is complete, and it is not already `running`, `verifying`, or `done`. A linked open PR makes that Phase the active Phase and MUST be reconciled before selecting new work.

## Reconstruction and reconciliation

GitHub is authoritative for live execution state. `resume plan #N` MUST work from a fresh session by loading the Plan issue, referenced Phase issues, their dependency metadata, linked PRs, and current repository/CI state. Chat history is never required.

Before execution, reconcile stale metadata conservatively. A merged PR does not by itself mark a Phase or Plan done: verify the Phase Definition of Done first. A closed dependency counts as satisfied only when its outcome meets the dependency described by the Phase. Conflicting or incomplete metadata fails closed and leaves the Plan blocked until reconciled.

## Next-runnable selection

Given the ordered `Phases` list in the Plan:

1. Reconcile any active linked PR before selecting another Phase.
2. Exclude phases whose dependencies are incomplete.
3. Exclude phases already `running`, `verifying`, or `done`.
4. Select the first remaining `ready` Phase in Plan order.
5. If none exists and unfinished phases remain, the Plan is `blocked`.
6. If all phases are complete, move the Plan to `verifying`; do not mark it `done` until every acceptance criterion is independently verified.

This rule is intentionally simple and deterministic. A blocked Plan consumes no active execution capacity. Human priority overrides remain authoritative and may reorder work explicitly in GitHub.

## Execution semantics

`plan create` creates a draft Plan using this contract. `plan inspect` reconstructs and reports Plan/Phase state. `plan ready` verifies the contract and hard preconditions before setting `ready`. `plan run` reconciles state, selects exactly one runnable Phase, and starts only that Phase. `plan resume` is equivalent to `plan run` after reconstruction from GitHub. `plan status` reports Plan state, phase progress, blockers, and next runnable Phase. `plan verify` independently checks Phase DoD or Plan acceptance criteria. `plan complete` is permitted only after successful Plan verification.

During implementation, deterministic repository checks are the normal feedback loop. Codex review is reserved for a stable merge-ready exact HEAD/base checkpoint and is never used to manufacture progress or implement its own feedback. Security-sensitive, credential, permission, breaking-contract, destructive, and release operations retain their human approval gates.

## Roadmap integration

Plans extend the issue-driven roadmap rather than replace it. Roadmap automation MUST distinguish Plans from ordinary candidates, expose Plan state and phase progress, and MUST NOT promote a blocked Plan merely because execution capacity exists. The dashboard SHOULD expose the next runnable Phase. Native GitHub dependency/sub-issue relationships may supplement this representation; the explicit issue metadata above remains the portable compatibility contract.

## Completion verification

Plan completion is a verification event, not a merge event. The verifier MUST re-read the Plan acceptance criteria and record evidence for each criterion. Only then may state become `done`. This separation prevents a sequence of successful PR merges from silently satisfying an outcome that was never demonstrated end to end.
