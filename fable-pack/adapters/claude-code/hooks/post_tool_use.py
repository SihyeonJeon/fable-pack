#!/usr/bin/env python3
from __future__ import annotations

import common
import eventlib


CONTEXT_TOOLS = {"Read", "Glob", "Grep", "LS", "WebSearch", "WebFetch"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
ORCHESTRATION_TOOLS = {"Task", "Agent", "TodoWrite", "ExitPlanMode", "EnterPlanMode", "Workflow"}


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    task_path = common.active_task_path(root)
    if task_path is None:
        return 0
    name = common.tool_name(payload)
    inp = common.tool_input(payload)
    response = common.tool_response(payload)
    session_id = str(payload.get("session_id") or "") or None
    # Reads/edits of the trace itself (fable-disk) are the agent doing gate
    # bookkeeping, not task context — recording them pollutes the corpus.
    path_value = str(inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or "")
    if name in (CONTEXT_TOOLS | EDIT_TOOLS) and common.is_disk_path(path_value, root):
        return 0
    if name in CONTEXT_TOOLS:
        event = eventlib.log_context(task_path, name, inp, response, session_id=session_id)
        if name == "Read":
            eventlib.log_observation_placeholder(task_path, event)
    elif name in EDIT_TOOLS:
        eventlib.log_edit(task_path, name, inp, allowed=True, session_id=session_id)
    elif name in ORCHESTRATION_TOOLS:
        eventlib.log_orchestration(task_path, name, inp, response, session_id=session_id)
    elif name == "Bash":
        eventlib.log_command(task_path, inp, response, session_id=session_id)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        # A pack bug must never crash the session or dump a traceback into
        # the transcript; surface one line and stay non-blocking.
        import sys as _sys

        print(f"fable-pack hook error ({__file__.rsplit('/', 1)[-1]}): {exc}", file=_sys.stderr)
        raise SystemExit(0)
