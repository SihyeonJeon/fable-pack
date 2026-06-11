#!/usr/bin/env python3
from __future__ import annotations

import common
import eventlib
import tracelib
import validate


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    task_path = common.active_task_path(root)
    if task_path is None:
        return 0
    # Capture the visible assistant turn: approach explanations, trade-off
    # narration, and final summaries are decision artifacts.
    text = tracelib.last_assistant_text(payload)
    if text:
        session_id = str(payload.get("session_id") or "") or None
        eventlib.log_assistant_text(task_path, text, session_id=session_id)
    # Before any implementation happened the done gate is trivially failing;
    # warning on every stop would be noise. Warn only once edits exist.
    if not tracelib.read_jsonl(task_path / "edit_log.jsonl"):
        return 0
    result = validate.validate_task(task_path.name, root, gate="done")
    if not result.ok:
        # Re-injecting an identical error list every turn wastes context
        # tokens; warn only when the gate state actually changes.
        digest = tracelib.sha256_text("\n".join(result.errors))
        state = task_path / ".warned_done_errors.sha"
        if state.exists() and state.read_text(encoding="utf-8").strip() == digest:
            return 0
        state.write_text(digest + "\n", encoding="utf-8")
        common.warn("done gate is not passing. `pack task done` will block until these are fixed:\n" + "\n".join(f"- {e}" for e in result.errors))
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
