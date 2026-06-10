#!/usr/bin/env python3
from __future__ import annotations

import common
import eventlib
import tracelib


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    # Stay completely silent (and write nothing) in projects that never
    # opted in: no fable-disk creation, no agent-visible message.
    if tracelib.recording_mode(root) != "on":
        return 0
    tracelib.ensure_disk(root)
    active = tracelib.read_active(root)
    model_id = tracelib.model_id_from_sources(payload)
    if active:
        task_path = common.active_task_path(root)
        if task_path is not None:
            eventlib.log_lifecycle(
                task_path,
                "session_start",
                {"source": payload.get("source"), "model_id": model_id},
                session_id=str(payload.get("session_id") or "") or None,
            )
        print(f"fable-pack {tracelib.PACK_VERSION}: Fable trace active={active} model={model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
