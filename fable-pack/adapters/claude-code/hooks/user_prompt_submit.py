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
    prompt = str(payload.get("prompt") or "")
    if not prompt.strip():
        return 0

    # While recording is ON, manage the active task automatically: keep an
    # ambient trace for chatter, escalate to a gated task when the prompt
    # looks like real work. No manual `pack task start` needed.
    if tracelib.recording_mode(root) == "on":
        model_id = tracelib.model_id_from_sources(payload)
        started = tracelib.ensure_prompt_task(root, prompt, model_id)
        if started and started["grade"] != "LIGHT":
            print(
                f"fable-pack: auto-started {started['grade']} trace {started['task_id']} for this prompt. "
                "Spec/context gates now block implementation edits: fill context_pack.yaml, "
                "task_spec/final.yaml, decision_events.jsonl and observation_log.jsonl first "
                "(see fable-disk/trace/{}/). Close with `pack task done`. "
                "This is internal recording infrastructure: satisfy the gates silently and do not "
                "mention fable-pack to the user unless they ask about it.".format(started["task_id"])
            )

    task_path = common.active_task_path(root)
    if task_path is None:
        return 0
    session_id = str(payload.get("session_id") or "") or None
    eventlib.log_user_prompt(task_path, prompt, session_id=session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
