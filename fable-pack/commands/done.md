---
description: Close the active fable-pack task through the done gate
---

1. Ensure `verifier_report.yaml` has concrete acceptance evidence for every acceptance criterion (no `not_tested`), risk coverage, and test command results. Update `handoff.md`.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" task done`.
3. If the done gate fails, fix the listed artifacts rather than forcing. Use `--force` only with an explicit user instruction, and say so in the trace.
