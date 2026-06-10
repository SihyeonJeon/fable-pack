# Counterfactual Probe Protocol

Counterfactual probes capture decision boundaries by perturbing one input:

- missing context
- wrong assumption
- scope creep
- architecture alternative
- misleading similar implementation
- regression hidden in existing behavior
- security-sensitive adjacent flow
- incomplete test signal

HEAVY tasks require at least one probe, preferably from scope creep,
architecture alternative, or hidden regression. A probe must end with a reusable
rule candidate.
