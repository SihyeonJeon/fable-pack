#!/usr/bin/env python3
from __future__ import annotations

import common
import tracelib
import validate


IMPLEMENTATION_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    # Recording/enforcement is opt-in per project; stay inert when off.
    if tracelib.recording_mode(root) != "on":
        return 0
    name = common.tool_name(payload)
    inp = common.tool_input(payload)
    if name not in IMPLEMENTATION_TOOLS:
        return 0

    path_value = str(inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or "")
    if common.is_internal_path(path_value, root):
        return 0
    if common.bypass_enabled(payload):
        common.record_bypass(root, payload, "PACK_BYPASS during pre_tool_use")
        return 0

    task_path = common.active_task_path(root)
    if task_path is None:
        common.block("no ACTIVE task. Run `fable-pack/adapters/claude-code/scripts/pack task start --goal ...`.")

    meta = validate.tracelib.load_yaml(task_path / "meta.yaml")
    if meta.get("grade") == "LIGHT":
        return 0

    spec = validate.spec_gate(task_path, root)
    context = validate.context_gate(task_path, root)
    if not spec.ok or not context.ok:
        errors = spec.errors + context.errors
        # Full error list once per state; identical re-blocks get one line
        # instead of re-injecting the same wall of text.
        digest = tracelib.sha256_text("\n".join(errors))
        state = task_path / ".blocked_errors.sha"
        if state.exists() and state.read_text(encoding="utf-8").strip() == digest:
            common.block(
                f"implementation edit still blocked by the same {len(errors)} spec/context gate "
                "errors as the previous block (unchanged)."
            )
        state.write_text(digest + "\n", encoding="utf-8")
        common.block("implementation edit blocked until spec/context gates pass:\n" + "\n".join(f"- {e}" for e in errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
