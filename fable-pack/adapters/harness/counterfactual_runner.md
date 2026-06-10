# Counterfactual Runner

A harness may generate perturbations from the base task and write them under
`counterfactuals/<probe-id>.yaml`.

Required perturbation fields:

- type
- changed_user_goal
- changed_context
- injected_assumption

The result must include actual Fable behavior, reason refs, and a reusable rule
candidate.
