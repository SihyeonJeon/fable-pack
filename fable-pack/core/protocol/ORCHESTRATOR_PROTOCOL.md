# Fable-Pack Orchestrator Protocol

Version: 0.4-max

The pack records observable decision policy, not private chain of thought. Every
nontrivial decision must be attached to repository evidence and to the artifact it
changed.

## Phases

1. START: create `fable-disk/trace/<task-id>` with `pack task start`.
2. SPEC: classify task, write initial task_spec, define risks and non-goals.
3. CONTEXT: read `context_pack.must_read`, log observations per file.
4. PLAN: freeze allowed files, forbidden files, verifier contract, and worker contract.
5. IMPLEMENT: edit only after spec/context gates pass.
6. VERIFY: fill `verifier_report.yaml` with evidence for every acceptance criterion.
7. DONE: `pack task done` runs done_gate and closes ACTIVE only if evidence is complete.

## Enforcement Scope

Claude Code hooks enforce and record only when the active model id contains
`fable`. Unknown or non-Fable model ids are treated as no-op to avoid collecting
fallback traces as Fable reference data.

## Evidence Order

1. Machine-collected behavior: context_log, edit_log, command_log, diffs, test output.
2. Structured audit: observation_log, decision_events, context_pack, plan_graph.
3. Model-authored interpretation: task_spec, self_review, rule_candidates.
4. Human label: human_review.

When these conflict, prefer the lower-numbered tier.
