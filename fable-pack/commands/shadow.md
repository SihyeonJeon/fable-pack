---
description: Scaffold and run a comparison-trace (shadow) pair for the active task
---

1. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" shadow scaffold --model <comparison-model-id>` (model id from $ARGUMENTS; default `claude-opus-4-8`). This creates `shadow/<model>/trace/` with copied input/repo snapshots, an empty task_spec template, and `critiques.yaml`.
2. Produce the comparison trace through SPEC/CONTEXT/PLAN only (no implementation), filling `shadow/<model>/trace/task_spec/final.yaml` and `decision_events.jsonl`.
3. Run `python3 "${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/scripts/pack" shadow run --fallback-model <model> --fallback-trace <scaffolded trace path>` to compute `delta.yaml` and the rule patch.
4. Record concrete gaps in `critiques.yaml`; HEAVY golden promotion requires the delta to exist.
