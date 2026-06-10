# State Mapping

| Harness concept | fable-pack artifact |
| --- | --- |
| run id | `fable-disk/trace/<task-id>` |
| active run pointer | `fable-disk/trace/ACTIVE` |
| input prompt | `input_snapshot.yaml.raw_user_goal` |
| repo state | `repo_snapshot.yaml` |
| orchestration spec | `task_spec/final.yaml` |
| worker dispatch | `worker_contracts/*.yaml` |
| verifier approval | `verifier_report.yaml` |
| comparison delta | `shadow/<fallback-model-id>/delta.yaml` |
| golden label | `human_review.yaml` |

Harness adapters should pass an explicit project root into `tracelib` instead of
assuming current working directory.
