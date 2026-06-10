# Decision Event Protocol

`decision_events.jsonl` is a machine-readable audit of observable decision
transitions. It must not ask for private reasoning. It records:

- what triggered the decision
- what observation or missing signal caused it
- which option was chosen
- which alternatives were rejected and why
- which artifact changed because of the decision

Required STANDARD event types:

- `task_classification`
- `context_selection`
- `requirement_inference`
- `rejected_alternative`
- `acceptance_evidence_selection`

Additional HEAVY event types:

- `architecture_boundary`
- `risk_escalation`
- `non_goal_boundary`
- `worker_contract_boundary`
- `verifier_gate_boundary`
- `rollback_boundary`
- `shadow_delta_interpretation`
- `counterfactual_boundary`

Each event must include `artifact_updates`. Rejected options must include a
category.
