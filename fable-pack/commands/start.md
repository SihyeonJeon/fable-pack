---
description: Start a fable-pack trace task for the current goal
---

Start a fable-pack reference trace for this task.

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" task grade --goal "$ARGUMENTS"` to estimate the grade.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" task start --goal "$ARGUMENTS" --grade <estimated-grade> --task-type <inferred-task-type> --model fable`.
3. Before any implementation edit, fill `fable-disk/trace/<task-id>/context_pack.yaml` and `task_spec/final.yaml`, and log decisions with `pack log decision` and observations with `pack log observation`. The PreToolUse gate blocks edits until spec and context gates pass.

Goal: $ARGUMENTS
