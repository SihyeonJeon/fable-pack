---
description: Show the merged time-ordered decision timeline of a trace
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" timeline` (add `--task-id <id>` from $ARGUMENTS for a closed task) and present the flow: prompt → reads → observations → decisions → plan → edits → commands → narration. Highlight observations marked `[understanding-changed]` and any `(todo)` decision slots still unfilled.
