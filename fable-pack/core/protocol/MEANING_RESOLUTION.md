# Task Meaning Resolution

Answer these questions before implementation and encode the answers in
`task_spec/final.yaml`, `context_pack.yaml`, and `decision_events.jsonl`.

1. Classification: primary type, secondary types, complexity, blast radius.
2. Precedent: similar implementation paths, commits, PRs, or symbols.
3. Contact surface: policies, conventions, invariants, and architecture boundaries.
4. Implicit requirements: behavior and regression targets the user did not name.
5. Misread scope: adjacent work that must become non-goals.
6. Assumptions: confidence, blocking status, default if unanswered.
7. Evidence: command or concrete manual procedure for every acceptance criterion.
8. Rejected alternatives: tempting shortcut, architecture alternative, scope boundary.
9. Context selection: why each must_read file was selected.
10. Verifier contract: what the verifier must check independent of the implementer.

Every answer needs a reference to a path, symbol, command output, observation, or
decision event. Generic assurances are invalid.
