# Shadow Protocol

Shadow runs compare a reviewed reference trace with a second, independent
trace of the same task to find gaps in the *written* process — checklist
items, gate rules, and spec sections that the reference captured but the
documentation did not yet require. The unit of comparison is the recorded
artifact, and the output is a documentation patch.

Compare:

- task classification
- context selection
- inferred requirements
- non-goals
- rejected alternatives
- architecture constraints
- risk register
- acceptance criteria
- verifier contract
- worker contract

HEAVY tasks require `shadow/<fallback-model-id>/delta.yaml`. Any blocking
omission requires a patch (`distillation_patch.yaml`) that converts the gap
into a schema field, gate rule, playbook checklist item, invariant, or
example candidate — i.e. the process documentation is updated so the same
omission cannot silently happen again.
