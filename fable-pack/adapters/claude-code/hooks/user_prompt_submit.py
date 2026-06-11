#!/usr/bin/env python3
from __future__ import annotations

import json

import common
import eventlib
import tracelib

TOGGLE_COMMANDS = {"/fable-pack:on": "on", "/fable-pack:off": "off"}


def handle_toggle(prompt: str, root) -> bool:
    """Intercept on/off as a pure toggle: block the prompt before it reaches
    the model and surface only a notification."""
    mode = TOGGLE_COMMANDS.get(prompt.strip())
    if mode is None:
        return False
    tracelib.set_recording_mode(mode, root)
    if mode == "on":
        message = "fable-pack: recording ON — the first Fable prompt starts the trace (off with /fable-pack:off)"
    else:
        active = tracelib.read_active(root)
        if active:
            task_path = tracelib.task_dir(active, root)
            meta = tracelib.load_yaml(task_path / "meta.yaml")
            meta["timestamp_end"] = tracelib.utc_now()
            meta.setdefault("phase_transitions", []).append({"phase": "DONE", "ts": tracelib.utc_now()})
            tracelib.write_yaml(task_path / "meta.yaml", meta)
            tracelib.clear_active(root)
            message = f"fable-pack: recording OFF — closed {active}"
        else:
            message = "fable-pack: recording OFF"
    print(json.dumps({"decision": "block", "reason": message}))
    return True


def main() -> int:
    payload = common.read_payload()
    if not common.should_run(payload):
        return 0
    root = common.project_root()
    prompt = str(payload.get("prompt") or "")
    if not prompt.strip():
        return 0
    if handle_toggle(prompt, root):
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
