from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import tracelib


def log_context(
    task_path: Path,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_response: Any = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    path = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
        or tool_input.get("pattern")
        or tool_input.get("query")
        or ""
    )
    event = {
        "event_type": tool_name,
        "path": path,
        "tool_input": scrub(tool_input),
        "response_summary": summarize(tool_response),
    }
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "context_log.jsonl", event)


def log_observation_placeholder(
    task_path: Path, context_event: Dict[str, Any], reason: str = "hook scaffold"
) -> Optional[Dict[str, Any]]:
    path = context_event.get("path", "")
    # One placeholder per path per task: re-reads add no new fill obligation,
    # and repeated UNFILLED rows are pure log bloat.
    existing = tracelib.read_jsonl(task_path / "observation_log.jsonl")
    if any(event.get("path") == path for event in existing):
        return None
    event = {
        "source_event": f"context_log:seq={context_event.get('seq')}",
        "path": context_event.get("path", ""),
        "symbols": [],
        "extracted_facts": [
            {
                "fact": "UNFILLED: add the repository fact extracted from this read.",
                "supports": [],
                "confidence": "low",
            }
        ],
        "changed_task_understanding": False,
        "caused_updates": [],
        "status": "placeholder",
        "reason": reason,
    }
    return tracelib.append_jsonl(task_path / "observation_log.jsonl", event)


def log_edit(
    task_path: Path,
    tool_name: str,
    tool_input: Dict[str, Any],
    allowed: Optional[bool] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or ""
    event = {
        "event_type": tool_name,
        "path": path,
        "allowed_by_gate": allowed,
        "tool_input_summary": summarize(tool_input),
    }
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "edit_log.jsonl", event)


def log_command(
    task_path: Path,
    tool_input: Dict[str, Any],
    tool_response: Any = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    command = redact_secrets(str(tool_input.get("command") or tool_input.get("cmd") or ""))
    event = {
        "command": command,
        "is_test_candidate": looks_like_test(command),
        "response_summary": summarize(tool_response),
    }
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "command_log.jsonl", event)


def log_orchestration(
    task_path: Path,
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_response: Any = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record planning/delegation tool calls: plans, todo decompositions, subagent dispatches.

    Plans and delegation prompts are stored near-full (not the 500-char scrub
    truncation) because they are primary thinking artifacts for replay.
    """
    event: Dict[str, Any] = {
        "event_type": tool_name,
        "tool_input_summary": summarize(tool_input),
        "response_summary": summarize(tool_response),
    }
    plan = tool_input.get("plan")
    if isinstance(plan, str) and plan.strip():
        event["plan_full"] = redact_secrets(plan)[:20000]
    prompt = tool_input.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        event["prompt_full"] = redact_secrets(prompt)[:20000]
    description = tool_input.get("description")
    if isinstance(description, str) and description.strip():
        event["description"] = redact_secrets(description)[:500]
    todos = tool_input.get("todos")
    if isinstance(todos, list):
        event["todos"] = scrub(todos)
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "orchestration_log.jsonl", event)


def log_user_prompt(task_path: Path, prompt: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "event_type": "user_prompt",
        "prompt": redact_secrets(prompt)[:20000],
    }
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "user_prompt_log.jsonl", event)


def log_assistant_text(task_path: Path, text: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Record the visible assistant turn text; dedup against the previous entry."""
    cleaned = redact_secrets(text).strip()
    if not cleaned:
        return None
    log_path = task_path / "assistant_log.jsonl"
    digest = tracelib.sha256_text(cleaned)
    existing = tracelib.read_jsonl(log_path)
    if existing and existing[-1].get("sha256") == digest:
        return None
    event: Dict[str, Any] = {
        "event_type": "assistant_turn",
        "text": cleaned[:20000],
        "sha256": digest,
    }
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(log_path, event)


def log_lifecycle(
    task_path: Path,
    event_type: str,
    detail: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record session boundaries and compactions so multi-session timelines reconstruct."""
    event: Dict[str, Any] = {"event_type": event_type, **scrub(detail)}
    if session_id:
        event["session_id"] = session_id
    return tracelib.append_jsonl(task_path / "context_log.jsonl", event)


def log_decision(
    task_path: Path,
    phase: str,
    event_type: str,
    trigger: str,
    decision: str,
    artifact_updates: List[str],
    observation_refs: Optional[List[Dict[str, Any]]] = None,
    rejected_options: Optional[List[Dict[str, Any]]] = None,
    confidence_before: str = "low",
    confidence_after: str = "medium",
    next_expected_signal: str = "",
) -> Dict[str, Any]:
    event = {
        "phase": phase,
        "event_type": event_type,
        "trigger": trigger,
        "observation_refs": observation_refs or [],
        "hypothesis_before": "",
        "decision": decision,
        "rejected_options": rejected_options or [],
        "confidence_before": confidence_before,
        "confidence_after": confidence_after,
        "next_expected_signal": next_expected_signal,
        "artifact_updates": artifact_updates,
    }
    return tracelib.append_jsonl(task_path / "decision_events.jsonl", event)


SECRET_VALUE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[ousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?key|secret|token|password|passwd|authorization)\s*[=:]\s*)(\"[^\"]+\"|'[^']+'|\S+)"),
]


def redact_secrets(text: str) -> str:
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda m: m.group(1) + "<redacted>", text)
        else:
            text = pattern.sub("<redacted>", text)
    return text


def scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("<redacted>" if secretish(k) else scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        value = redact_secrets(value)
        if len(value) > 500:
            return value[:500] + "...<truncated>"
    return value


def secretish(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ["token", "secret", "password", "api_key", "apikey", "authorization"])


def summarize(value: Any) -> str:
    if value is None:
        return ""
    text = str(scrub(value))
    return text[:1000] + ("...<truncated>" if len(text) > 1000 else "")


def looks_like_test(command: str) -> bool:
    lowered = command.lower()
    return any(
        token in lowered
        for token in [
            "test",
            "pytest",
            "unittest",
            "vitest",
            "jest",
            "playwright",
            "xcodebuild",
            "cargo test",
            "go test",
            "npm run build",
        ]
    )
