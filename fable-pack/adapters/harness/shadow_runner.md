# Shadow Runner

This pack does not run comparison sessions itself. A harness that wants a second trace for documentation-gap analysis may:

1. Copy `input_snapshot.yaml` and `repo_snapshot.yaml` into a new comparison trace.
2. Produce the comparison trace only through SPEC, CONTEXT, and PLAN.
3. Call `compare.make_shadow_delta(base_task_id, fallback_model_id, fallback_trace_ref)`.
4. Attach the generated `omission_to_rule_patch.yaml` to rule candidate review.
