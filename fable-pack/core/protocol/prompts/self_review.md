# Self Review Prompt

Review the frozen trace without modifying original artifacts.

Return:

- initial_vs_final_understanding
- observation refs that caused the delta
- missed_or_weak_items with severity
- potential_worker_confusions
- patch target for each issue: schema, gate, playbook, invariant, example, or none

Do not add new facts that are not supported by context_log, observation_log, or
decision_events.
