from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PACK_VERSION = "0.5"
PROTOCOL_VERSION = "0.4-max"
PHASES = ["START", "SPEC", "CONTEXT", "PLAN", "IMPLEMENT", "VERIFY", "DONE"]


def plugin_version(start: "Optional[Path]" = None) -> "Optional[str]":
    manifest = pack_root(start) / ".claude-plugin" / "plugin.json"
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except Exception:
        return None
GRADES = ["LIGHT", "STANDARD", "HEAVY"]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_pack_install(candidate: Path) -> bool:
    """True only for a real per-project pack install, not any directory that
    happens to be named fable-pack (e.g. a checkout of this repo in $HOME)."""
    return (candidate / "fable-pack" / "PACK_VERSION").is_file()


def _is_pack_disk(candidate: Path) -> bool:
    disk = candidate / "fable-disk"
    return (disk / "trace").is_dir() and (disk / "config").is_dir()


def _escape_disk(path: Path) -> Path:
    """A session launched (or a shell parked) inside fable-disk/... must
    resolve to the real project, never to the recording tree itself."""
    parts = path.parts
    if "fable-disk" in parts:
        return Path(*parts[: parts.index("fable-disk")])
    return path


def project_root(start: Optional[Path] = None) -> Path:
    explicit = os.environ.get("FABLE_PACK_PROJECT_ROOT")
    if explicit:
        return Path(explicit).resolve()
    # Set by Claude Code for hook/plugin executions; with a global plugin the
    # target project has no fable-pack/ directory to walk to.
    claude_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_project:
        return _escape_disk(Path(claude_project).resolve())
    current = _escape_disk((start or Path.cwd()).resolve())
    for candidate in [current, *current.parents]:
        if _is_pack_install(candidate) or _is_pack_disk(candidate):
            return candidate
    return current


def pack_root(start: Optional[Path] = None) -> Path:
    explicit = os.environ.get("FABLE_PACK_ROOT")
    if explicit:
        return Path(explicit).resolve()
    root = project_root(start)
    return root / "fable-pack"


def disk_root(root: Optional[Path] = None) -> Path:
    return (root or project_root()) / "fable-disk"


def trace_root(root: Optional[Path] = None) -> Path:
    return disk_root(root) / "trace"


def corpus_root(root: Optional[Path] = None) -> Path:
    return disk_root(root) / "corpus"


def ensure_disk(root: Optional[Path] = None) -> Path:
    disk = disk_root(root)
    for path in [
        disk,
        trace_root(root),
        corpus_root(root),
        disk / "config",
        corpus_root(root) / "fable_golden",
        corpus_root(root) / "flawed_examples",
        corpus_root(root) / "shadow_deltas",
        corpus_root(root) / "counterfactuals",
        corpus_root(root) / "distilled_rules",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    index = corpus_root(root) / "index.jsonl"
    if not index.exists():
        index.touch()
    return disk


def active_file(root: Optional[Path] = None) -> Path:
    return trace_root(root) / "ACTIVE"


def read_active(root: Optional[Path] = None) -> Optional[str]:
    path = active_file(root)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def set_active(task_id: str, root: Optional[Path] = None) -> None:
    ensure_disk(root)
    active_file(root).write_text(task_id + "\n", encoding="utf-8")


def clear_active(root: Optional[Path] = None) -> None:
    path = active_file(root)
    if path.exists():
        path.unlink()


def task_dir(task_id: Optional[str] = None, root: Optional[Path] = None) -> Path:
    task_id = task_id or read_active(root)
    if not task_id:
        raise RuntimeError("No active fable-pack task. Run `pack task start` first.")
    return trace_root(root) / task_id


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_git(args: List[str], root: Optional[Path] = None) -> str:
    cwd = root or project_root()
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return "unavailable"
    if proc.returncode != 0:
        return "unavailable"
    return proc.stdout.strip() or "unavailable"


def repo_state(root: Optional[Path] = None) -> Dict[str, Any]:
    root = root or project_root()
    status = run_git(["status", "--short"], root)
    diff = run_git(["diff"], root)
    return {
        "commit": run_git(["rev-parse", "HEAD"], root),
        "branch": run_git(["branch", "--show-current"], root),
        "status": "" if status == "unavailable" else status,
        "dirty_state": bool(status and status != "unavailable"),
        "diff_hash_before": sha256_text(diff if diff != "unavailable" else ""),
    }


def load_yaml(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data or {}
    except Exception:
        return json.loads(text)


def dump_yaml(data: Dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    except Exception:
        return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"


def write_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")


def append_jsonl(path: Path, event: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if "ts" not in event:
        event["ts"] = utc_now()
    with path.open("a+", encoding="utf-8") as fh:
        # Parallel tool calls fire concurrent hook processes; lock so seq
        # assignment and the write are atomic per event.
        try:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        if "seq" not in event:
            fh.seek(0)
            event["seq"] = sum(1 for line in fh if line.strip()) + 1
        fh.seek(0, os.SEEK_END)
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=False) + "\n")
    return event


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def next_seq(path: Path) -> int:
    return len(read_jsonl(path)) + 1


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def transcript_tail(payload: Optional[Dict[str, Any]] = None, size: int = 262144) -> List[Dict[str, Any]]:
    """Parse the tail of the Claude Code transcript JSONL into entries (oldest first)."""
    payload = payload or {}
    transcript = payload.get("transcript_path")
    if not transcript:
        return []
    path = Path(str(transcript))
    if not path.is_file():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            end = fh.tell()
            fh.seek(max(0, end - size))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    entries = []
    for line in tail.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def model_id_from_transcript(payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve the active model from the Claude Code transcript JSONL.

    Hook payloads do not carry a model field and Claude Code does not export
    model env vars to hook subprocesses, so the transcript is the only source
    that reflects the live session (including mid-session /model switches).
    """
    for entry in reversed(transcript_tail(payload)):
        message = entry.get("message")
        if isinstance(message, dict):
            model = message.get("model")
            if isinstance(model, str) and model:
                return model
    return None


def last_assistant_text(payload: Optional[Dict[str, Any]] = None, max_chars: int = 20000) -> Optional[str]:
    """Extract the visible text of the latest assistant turn from the transcript.

    Thinking blocks are deliberately skipped: the pack records decision
    artifacts, not private chain of thought.
    """
    # One assistant turn can span several transcript entries; walk backwards
    # collecting assistant text until the previous user message is reached.
    collected: List[str] = []
    for entry in reversed(transcript_tail(payload, size=524288)):
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "user":
            content = message.get("content")
            only_tool_results = isinstance(content, list) and all(
                isinstance(block, dict) and block.get("type") == "tool_result" for block in content
            )
            if only_tool_results:
                continue
            if collected:
                break
            continue
        if role != "assistant":
            continue
        content = message.get("content")
        parts: List[str] = []
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
        if parts:
            collected = parts + collected
    if not collected:
        return None
    return "\n\n".join(collected).strip()[:max_chars] or None


def model_id_from_sources(payload: Optional[Dict[str, Any]] = None) -> str:
    payload = payload or {}
    explicit = os.environ.get("FABLE_PACK_MODEL_ID")
    if explicit:
        return explicit

    from_transcript = model_id_from_transcript(payload)
    if from_transcript:
        return from_transcript

    env_keys = [
        "CLAUDE_CODE_MODEL",
        "CLAUDE_MODEL",
        "ANTHROPIC_MODEL",
        "MODEL",
    ]
    for key in env_keys:
        value = os.environ.get(key)
        if value:
            return value

    def walk(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            for key in ["model", "model_id", "active_model", "name"]:
                nested = value.get(key)
                if isinstance(nested, str):
                    return nested
            for nested in value.values():
                found = walk(nested)
                if found:
                    return found
        return None

    return walk(payload) or "unknown"


def is_fable_model(model_id: str) -> bool:
    if os.environ.get("FABLE_PACK_FORCE") == "1":
        return True
    lowered = (model_id or "").lower()
    return "fable" in lowered


def should_record(payload: Optional[Dict[str, Any]] = None) -> bool:
    return is_fable_model(model_id_from_sources(payload))


HEAVY_GOAL_KEYWORDS = [
    "auth",
    "authentication",
    "authorization",
    "permission",
    "billing",
    "payment",
    "migration",
    "schema",
    "oauth",
    "session",
    "security",
    "data deletion",
    "rollback",
    "인증",
    "인가",
    "권한",
    "결제",
    "과금",
    "빌링",
    "마이그레이션",
    "스키마",
    "세션",
    "보안",
    "데이터 삭제",
    "롤백",
]

STANDARD_GOAL_KEYWORDS = [
    "implement",
    "refactor",
    "feature",
    "fix",
    "bug",
    "add",
    "rewrite",
    "redesign",
    "구현",
    "리팩터링",
    "리팩토링",
    "기능",
    "수정",
    "버그",
    "추가",
    "개선",
    "만들어",
    "작성",
]

KOREAN_INTERROGATIVE_ENDINGS = ("까", "니", "는가", "은가", "을까", "겠나", "한가")


def estimate_grade(goal: str) -> str:
    lowered = goal.lower()
    if any(keyword in lowered for keyword in HEAVY_GOAL_KEYWORDS):
        return "HEAVY"
    if any(keyword in lowered for keyword in STANDARD_GOAL_KEYWORDS):
        return "STANDARD"
    if len(goal.split()) <= 8:
        return "LIGHT"
    return "STANDARD"


def estimate_prompt_grade(prompt: str) -> str:
    """Grade a raw conversational prompt for auto-escalation.

    Unlike estimate_grade (used for deliberately written goals, where long
    text implies work), a prompt is casual by default: questions never
    escalate, and only explicit work keywords do.
    """
    stripped = prompt.strip()
    if stripped.endswith(("?", "？")) or stripped.endswith(KOREAN_INTERROGATIVE_ENDINGS):
        return "LIGHT"
    lowered = stripped.lower()
    if any(keyword in lowered for keyword in HEAVY_GOAL_KEYWORDS):
        return "HEAVY"
    if any(keyword in lowered for keyword in STANDARD_GOAL_KEYWORDS):
        return "STANDARD"
    return "LIGHT"


def mode_file(root: Optional[Path] = None) -> Path:
    return disk_root(root) / "config" / "MODE"


def recording_mode(root: Optional[Path] = None) -> str:
    path = mode_file(root)
    if not path.exists():
        return "off"
    value = path.read_text(encoding="utf-8").strip().lower()
    return value if value in ("on", "off") else "off"


def set_recording_mode(mode: str, root: Optional[Path] = None) -> None:
    ensure_disk(root)
    mode_file(root).write_text(mode + "\n", encoding="utf-8")


def ensure_prompt_task(root: Path, prompt: str, model_id: str) -> Optional[Dict[str, Any]]:
    """Auto-manage the active task from an incoming user prompt while recording is on.

    Returns a dict describing an auto-started task, or None when nothing changed.
    - no active task        -> start ambient LIGHT task
    - active ambient task and the prompt grades STANDARD/HEAVY
                            -> close ambient, start a gated task with the prompt as goal
    - active gated task     -> leave as is (prompt is just logged by the caller)
    """
    if prompt.lstrip().startswith("/"):
        return None
    active = read_active(root)
    if active:
        meta = load_yaml(task_dir(active, root) / "meta.yaml")
        if meta.get("task_type") != "ambient":
            return None
        grade = estimate_prompt_grade(prompt)
        if grade == "LIGHT":
            return None
        ambient_path = task_dir(active, root)
        meta["timestamp_end"] = utc_now()
        meta.setdefault("phase_transitions", []).append({"phase": "DONE", "ts": utc_now()})
        write_yaml(ambient_path / "meta.yaml", meta)
        task_path = scaffold_task(
            goal=prompt[:500],
            grade=grade,
            task_type="general",
            model_id=model_id,
            root=root,
        )
        return {"task_id": task_path.name, "grade": grade, "replaced_ambient": active}
    grade = estimate_prompt_grade(prompt)
    if grade == "LIGHT":
        task_path = scaffold_task(
            goal="ambient session recording",
            grade="LIGHT",
            task_type="ambient",
            model_id=model_id,
            root=root,
        )
        return {"task_id": task_path.name, "grade": "LIGHT", "replaced_ambient": None}
    task_path = scaffold_task(
        goal=prompt[:500],
        grade=grade,
        task_type="general",
        model_id=model_id,
        root=root,
    )
    return {"task_id": task_path.name, "grade": grade, "replaced_ambient": None}


def safe_task_id(raw: Optional[str] = None) -> str:
    if raw:
        cleaned = "".join(c if c.isalnum() or c in "-_." else "-" for c in raw.strip())
        cleaned = cleaned.strip("-_.")
        if cleaned:
            return cleaned[:96]
    return "task-" + utc_now().replace(":", "").replace("-", "").replace("Z", "z")


def scaffold_task(
    goal: str,
    grade: str = "STANDARD",
    task_type: str = "general",
    task_id: Optional[str] = None,
    model_id: Optional[str] = None,
    root: Optional[Path] = None,
) -> Path:
    root = root or project_root()
    ensure_disk(root)
    grade = grade.upper()
    if grade not in GRADES:
        raise ValueError(f"Unsupported grade: {grade}")
    explicit_id = task_id is not None
    task_id = safe_task_id(task_id)
    directory = trace_root(root) / task_id
    if not explicit_id:
        # Timestamp-based ids collide when two tasks start within the same
        # second (e.g. ambient close + gated auto-start); uniquify.
        base = task_id
        counter = 2
        while directory.exists():
            task_id = f"{base}-{counter}"
            directory = trace_root(root) / task_id
            counter += 1
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "task_spec").mkdir(exist_ok=True)
    (directory / "worker_contracts").mkdir(exist_ok=True)
    (directory / "shadow").mkdir(exist_ok=True)
    (directory / "counterfactuals").mkdir(exist_ok=True)
    for name in [
        "context_log.jsonl",
        "observation_log.jsonl",
        "decision_events.jsonl",
        "edit_log.jsonl",
        "command_log.jsonl",
        "user_prompt_log.jsonl",
        "orchestration_log.jsonl",
        "assistant_log.jsonl",
    ]:
        (directory / name).touch(exist_ok=True)

    repo = repo_state(root)
    model_id = model_id or model_id_from_sources()
    meta = {
        "task_id": task_id,
        "pack_version": PACK_VERSION,
        "versions": {
            "runtime": PACK_VERSION,
            "protocol": PROTOCOL_VERSION,
            "plugin": plugin_version(root),
        },
        "model": {
            "provider": "anthropic",
            "model_id": model_id,
            "role": "fable_reference" if is_fable_model(model_id) else "fallback_shadow",
        },
        "environment": "claude-code",
        "context_log_status": "VERIFIED",
        "grade": grade,
        "task_type": task_type,
        "commit": repo["commit"],
        "branch": repo["branch"],
        "timestamp_start": utc_now(),
        "timestamp_end": None,
        "phase_transitions": [{"phase": "START", "ts": utc_now()}],
        "golden_rating": None,
        "human_label_status": "pending" if grade == "HEAVY" else "not_required",
        "bypass_events": [],
    }
    input_snapshot = {
        "task_id": task_id,
        "raw_user_goal": goal,
        "normalized_goal": goal.strip(),
        "prompt_stack": {
            "system_prompt_hash": "unknown",
            "harness_prompt_hash": "none",
            "project_instructions_hash": "unknown",
            "pack_protocol_hash": sha256_text(PACK_VERSION),
        },
        "model_settings": {
            "model_id": model_id,
            "temperature": None,
            "max_tokens": None,
        },
        "tool_environment": {
            "tools_enabled": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
            "hooks_enabled": True,
            "enforcement_level": 2,
        },
        "repo_input": {
            "commit": repo["commit"],
            "branch": repo["branch"],
            "dirty_state": repo["dirty_state"],
            "diff_hash_before": repo["diff_hash_before"],
            "dependency_lock_hash": lock_hash(root),
        },
    }
    repo_snapshot = {
        "commit": repo["commit"],
        "branch": repo["branch"],
        "status": repo["status"],
        "diff_hash_before": repo["diff_hash_before"],
        "diff_hash_after": None,
        "important_paths": [],
        "lockfiles": list_lockfiles(root),
    }
    context_pack = {
        "task_id": task_id,
        "task_type": task_type,
        "must_read": [],
        "should_read": [],
        "similar_implementations": [],
        "conventions": [],
        "known_hazards": [],
        "forbidden_context_shortcuts": [],
        "no_precedent_justification": None,
    }
    spec = empty_task_spec(task_id, goal, task_type)
    write_yaml(directory / "meta.yaml", meta)
    write_yaml(directory / "input_snapshot.yaml", input_snapshot)
    write_yaml(directory / "repo_snapshot.yaml", repo_snapshot)
    write_yaml(directory / "context_pack.yaml", context_pack)
    write_yaml(directory / "task_spec" / "00_initial.yaml", with_revision(spec, "00_initial", None, []))
    write_yaml(directory / "task_spec" / "final.yaml", spec)
    write_yaml(directory / "verifier_report.yaml", empty_verifier_report(task_id))
    write_yaml(directory / "human_review.yaml", empty_human_review(task_id))
    write_yaml(directory / "rule_candidates.yaml", {"task_id": task_id, "draft_queue": []})
    write_yaml(directory / "distillation_patch.yaml", empty_distillation_patch(task_id, "self_review", "pending"))
    (directory / "handoff.md").write_text(f"# Handoff: {task_id}\n\nPending verification.\n", encoding="utf-8")
    set_active(task_id, root)
    append_jsonl(directory / "decision_events.jsonl", {
        "phase": "SPEC",
        "event_type": "task_classification",
        "trigger": "pack task start",
        "observation_refs": [],
        "hypothesis_before": "User goal has not been resolved against repository context.",
        "decision": f"Start {grade} trace for task_type={task_type}.",
        "rejected_options": [],
        "confidence_before": "low",
        "confidence_after": "low",
        "next_expected_signal": "Repository context scan and must_read selection.",
        "artifact_updates": ["meta.yaml", "input_snapshot.yaml", "task_spec/00_initial.yaml"],
    })
    # TODO skeletons for every decision type this grade requires: filling a
    # named slot misses less than remembering to create it. status=todo events
    # do NOT satisfy gates (validate filters them out).
    if grade in ("STANDARD", "HEAVY"):
        required = ["context_selection", "requirement_inference", "rejected_alternative", "acceptance_evidence_selection"]
        if grade == "HEAVY":
            required += [
                "architecture_boundary",
                "risk_escalation",
                "non_goal_boundary",
                "worker_contract_boundary",
                "verifier_gate_boundary",
                "rollback_boundary",
                "shadow_delta_interpretation",
                "counterfactual_boundary",
            ]
        for event_type in required:
            append_jsonl(directory / "decision_events.jsonl", {
                "status": "todo",
                "phase": "SPEC",
                "event_type": event_type,
                "trigger": "",
                "observation_refs": [],
                "hypothesis_before": "",
                "decision": "",
                "rejected_options": [],
                "confidence_before": "",
                "confidence_after": "",
                "next_expected_signal": "",
                "artifact_updates": [],
            })
    return directory


def empty_task_spec(task_id: str, goal: str, task_type: str) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "user_goal": goal,
        "goal_interpretation": {
            "restated_goal": "",
            "ambiguities": [],
            "unstated_expectations": [],
        },
        "task_classification": {
            "primary_type": task_type,
            "secondary_types": [],
            "complexity": "medium",
            "blast_radius": "medium",
        },
        "repo_context": {
            "must_read": [],
            "similar_implementations": [],
            "architectural_constraints": [],
            "critical_invariants": [],
        },
        "inferred_requirements": {
            "functional": [],
            "non_functional": [],
            "security": [],
            "regression": [],
        },
        "non_goals": [],
        "assumptions": [],
        "rejected_alternatives": [],
        "risk_register": [],
        "acceptance_criteria": [],
        "rollback_plan": {
            "type": "not_applicable",
            "details": "Pending repository scan.",
            "evidence_ref": None,
        },
        "worker_dispatch_summary": {
            "workers_required": [],
            "dispatch_blockers": [],
        },
    }


def with_revision(spec: Dict[str, Any], revision_id: str, previous: Optional[str], changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = json.loads(json.dumps(spec))
    data["revision_meta"] = {
        "revision_id": revision_id,
        "previous_revision": previous,
        "changed_fields": changes,
    }
    return data


def empty_verifier_report(task_id: str) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "changed_files": [],
        "forbidden_file_check": {"touched_forbidden_file": False, "forbidden_files": []},
        "acceptance_evidence": [],
        "risk_coverage": [],
        "test_commands": [],
        "unplanned_changes": [],
        "verdict": "request_changes",
    }


def empty_human_review(task_id: str) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "reviewer": None,
        "review_date": None,
        "rating": None,
        "critical_omissions_found": [],
        "over_scoping_found": [],
        "under_scoping_found": [],
        "fable_specific_strengths": [],
        "should_become_few_shot": False,
        "should_become_playbook_rule": False,
        "should_become_gate_rule": False,
        "notes": "",
    }


def empty_distillation_patch(task_id: str, source_type: str, source_ref: str) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "source": {"type": source_type, "ref": source_ref},
        "patches": {
            "schema": [],
            "gate_rules": [],
            "playbook_rules": [],
            "examples": [],
            "invariants": [],
        },
    }


def list_lockfiles(root: Path) -> List[Dict[str, str]]:
    names = {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lockb",
        "Cargo.lock",
        "Gemfile.lock",
        "poetry.lock",
        "uv.lock",
        "requirements.txt",
    }
    result = []
    skip_dirs = {
        ".git",
        "node_modules",
        ".next",
        "dist",
        "build",
        ".venv",
        "venv",
        "__pycache__",
        "fable-disk",
    }
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in skip_dirs]
        current = Path(dirpath)
        for filename in filenames:
            if filename in names:
                path = current / filename
                result.append({"path": str(path.relative_to(root)), "hash": sha256_file(path)})
    return result


def lock_hash(root: Path) -> Optional[str]:
    lockfiles = list_lockfiles(root)
    if not lockfiles:
        return None
    return sha256_text(json.dumps(lockfiles, sort_keys=True))


TIMELINE_SOURCES = [
    ("user_prompt_log.jsonl", "PROMPT"),
    ("context_log.jsonl", "READ"),
    ("observation_log.jsonl", "OBSERVE"),
    ("decision_events.jsonl", "DECIDE"),
    ("orchestration_log.jsonl", "PLAN"),
    ("edit_log.jsonl", "EDIT"),
    ("command_log.jsonl", "RUN"),
    ("assistant_log.jsonl", "SAY"),
]


def _timeline_summary(kind: str, event: Dict[str, Any]) -> str:
    if kind == "PROMPT":
        return (event.get("prompt") or "")[:120]
    if kind == "READ":
        return f"{event.get('event_type', '')} {event.get('path', '')}"[:120]
    if kind == "OBSERVE":
        if event.get("status") == "placeholder":
            return f"placeholder {event.get('path', '')}"[:120]
        facts = event.get("extracted_facts") or []
        fact = facts[0].get("fact", "") if facts else ""
        marker = " [understanding-changed]" if event.get("changed_task_understanding") else ""
        return f"{event.get('path', '')}: {fact}{marker}"[:160]
    if kind == "DECIDE":
        if event.get("status") == "todo":
            return f"(todo) {event.get('event_type', '')}"
        return f"{event.get('event_type', '')}: {event.get('decision', '')}"[:160]
    if kind == "PLAN":
        return f"{event.get('event_type', '')}: {(event.get('plan_full') or event.get('prompt_full') or event.get('tool_input_summary') or '')}"[:160]
    if kind == "EDIT":
        return f"{event.get('event_type', '')} {event.get('path', '')}"[:120]
    if kind == "RUN":
        return (event.get("command") or "")[:120]
    if kind == "SAY":
        return (event.get("text") or "")[:160]
    return ""


def timeline(task_id: Optional[str] = None, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Reconstruct the working timeline of a task across every log stream.

    Output is ordered by timestamp (then per-file seq), which makes the
    recorded flow inspectable end to end: prompt -> reads -> observations ->
    decisions -> plan -> edits -> commands -> narration.
    """
    task_path = task_dir(task_id, root)
    entries: List[Dict[str, Any]] = []
    for filename, kind in TIMELINE_SOURCES:
        for event in read_jsonl(task_path / filename):
            entries.append({
                "ts": str(event.get("ts") or ""),
                "seq": event.get("seq") or 0,
                "kind": kind,
                "summary": _timeline_summary(kind, event),
            })
    meta = load_yaml(task_path / "meta.yaml")
    for transition in meta.get("phase_transitions") or []:
        entries.append({
            "ts": str(transition.get("ts") or ""),
            "seq": 0,
            "kind": "PHASE",
            "summary": str(transition.get("phase") or ""),
        })
    entries.sort(key=lambda e: (e["ts"], e["seq"]))
    return entries
