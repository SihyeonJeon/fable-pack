---
description: Turn on fable-pack recording for this project (auto-gates real work, until /fable-pack:off)
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" on` from the project root and report the result.

While ON:
- Every user prompt, file read, edit, command, plan, and subagent dispatch is auto-recorded to `fable-disk/trace/<task-id>/`.
- Casual prompts stay in an ambient LIGHT trace with no blocking.
- Prompts that look like real work (implementation, refactor, auth/payment/migration, ...) automatically start a gated STANDARD/HEAVY trace: implementation edits are blocked until `context_pack.yaml`, `task_spec/final.yaml`, decision events, and observations are filled.

The state persists across sessions until `/fable-pack:off`.

If the user supplied a goal in $ARGUMENTS, pass it: `pack on --goal "$ARGUMENTS"`.
