---
description: Promote a reviewed trace into the golden corpus
---

1. Confirm `human_review.yaml` of the target task has a rating (`exemplary`/`normal` for golden, `flawed` for negative examples). If missing, ask the user to review first — do not self-assign a rating.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" corpus promote --task-id <task-id>` (omit `--task-id` for the active task: $ARGUMENTS).
3. Report the bucket and corpus path from the output.
