# Rule Extraction Prompt

Convert each omission, counterfactual boundary, or human-review issue into one
of:

- schema field
- gate rule
- task playbook rule
- invariant
- good or bad example

Every patch must include source artifact, source task id, and expected failure it
prevents.
