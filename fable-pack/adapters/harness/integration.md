# Harness Integration

This adapter consumes `fable-pack/core/rules/gate_rules.yaml` and writes durable
state under `fable-disk/trace` unless the harness injects another trace root.

## Phase Gate Registration

- START -> SPEC: require `meta.yaml` and `input_snapshot.yaml`
- SPEC -> CONTEXT: require `task_spec/00_initial.yaml`
- CONTEXT -> PLAN: require `context_pack.yaml`, `context_log.jsonl`, `observation_log.jsonl`
- PLAN -> IMPLEMENT: run spec_gate, context_gate, and HEAVY plan_gate
- IMPLEMENT -> VERIFY: require edit_log and command_log to be current
- VERIFY -> DONE: run done_gate

## Durable State Mapping

- `fable-disk/trace/<task-id>` maps to harness run state.
- `task_spec/final.yaml` maps to worker dispatch contract source.
- `verifier_report.yaml` maps to harness approval gate.
- `shadow/<fallback-model-id>/delta.yaml` maps to second-trace comparison.
- `counterfactuals/*.yaml` maps to decision boundary probes.

## Conflict Policy

Core schemas are canonical for trace artifacts. Harness-specific fields may be
added under `harness_extensions`, but canonical field names must not be copied
or forked.

## Fable Reference Mode

When the selected model id contains `fable`, the harness marks
`meta.model.role=fable_reference` and allows corpus promotion if all quality
gates pass.

## Comparison Run Mode

A comparison run reuses the same `input_snapshot.yaml` and
`repo_snapshot.yaml` so both traces describe the identical task input.
The comparison trace must not overwrite the reference trace.

## Shadow Comparison Mode

Call `compare.make_shadow_delta(base_task_id, fallback_model_id,
fallback_trace_ref)` after the fallback trace reaches PLAN.

## Counterfactual Mode

Create a perturbation in `counterfactuals/<probe-id>.yaml` and record whether
the decision boundary changed as expected.
