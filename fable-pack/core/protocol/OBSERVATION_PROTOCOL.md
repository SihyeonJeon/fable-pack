# Observation Protocol

`context_log.jsonl` says what was read. `observation_log.jsonl` says what was
found and what artifact changed because of it.

For STANDARD tasks, each `must_read` file needs at least one observation or a
recorded "no relevant fact found" explanation.

For HEAVY tasks:

- every `must_read` file needs an observation
- at least one observation must set `changed_task_understanding: true`
- at least three observation -> decision -> artifact chains should exist

Observations must be concrete repository facts. Do not record generic summaries.
