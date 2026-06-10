#!/usr/bin/env python3
from __future__ import annotations

import common
import eventlib


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    task_path = common.active_task_path(root)
    if task_path is None:
        return 0
    session_id = str(payload.get("session_id") or "") or None
    eventlib.log_lifecycle(
        task_path,
        "compaction",
        {
            "trigger": payload.get("trigger"),
            "custom_instructions": payload.get("custom_instructions"),
        },
        session_id=session_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
