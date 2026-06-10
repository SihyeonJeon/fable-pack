# Solo Protocol

Instruction-only mode has no mechanical enforcement and must not enter Fable
golden corpus. Use it only for smoke evidence or manual fallback runs.

Every response starts with:

```text
[phase: SPEC | CONTEXT | PLAN | IMPLEMENT | VERIFY | DONE]
[task: <id>]
[grade: LIGHT|STANDARD|HEAVY]
```

Rules:

1. Do not output implementation code before `task_spec/final.yaml` is approved.
2. Fill every template field. If not applicable, write a reason.
3. Mark context logs as `UNVERIFIED`.
4. End with an artifact completeness table.
5. Store traces under `fable-disk/trace/<task-id>`.
6. Do not promote instruction-only traces to `fable_golden`.
