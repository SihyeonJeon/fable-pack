# Example: a real gated bug-fix trace

Sanitized copy (home directory replaced with `~`) of an actual fable-pack
trace from this repository: a user-reported bug — recording silently landed
in the wrong directory — diagnosed, gated, fixed, and closed through the
done gate.

Read in this order:

1. `task_spec/final.yaml` — goal interpretation, inferred requirements, rejected alternatives, acceptance criteria
2. `context_pack.yaml` — what was read before acting, and why each file was selected
3. `decision_events.jsonl` — classification, context selection, requirement inference, rejected alternatives
4. `observation_log.jsonl` — facts extracted from reads, including the one that changed task understanding
5. `verifier_report.yaml` — evidence per acceptance criterion, risk coverage, approve verdict
6. `timeline.txt` — the whole flow reconstructed in time order (`pack timeline` output)
