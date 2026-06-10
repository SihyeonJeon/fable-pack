from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

PACK_ROOT = Path(__file__).resolve().parents[3]
LIB_ROOT = PACK_ROOT / "core" / "lib"
sys.path.insert(0, str(LIB_ROOT))

import eventlib  # noqa: E402
import tracelib  # noqa: E402
import validate  # noqa: E402


def read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_stdin": raw}


def tool_name(payload: Dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or payload.get("name") or "")


def tool_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = payload.get("tool_input") or payload.get("input") or payload.get("parameters") or {}
    return value if isinstance(value, dict) else {}


def tool_response(payload: Dict[str, Any]) -> Any:
    return payload.get("tool_response") or payload.get("response") or payload.get("result")


def project_root() -> Path:
    return tracelib.project_root()


def active_task_path(root: Optional[Path] = None) -> Optional[Path]:
    try:
        active = tracelib.read_active(root)
        if not active:
            return None
        return tracelib.task_dir(active, root)
    except Exception:
        return None


def _root_relative_first_part(path_value: str, root: Path) -> Optional[str]:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = root / path
    try:
        rel = path.resolve().relative_to(root.resolve())
    except Exception:
        return None
    return rel.parts[0] if rel.parts else None


def is_internal_path(path_value: str, root: Path) -> bool:
    return _root_relative_first_part(path_value, root) in {"fable-pack", "fable-disk"}


def is_disk_path(path_value: str, root: Path) -> bool:
    """True only for the recording directory itself (fable-disk)."""
    return _root_relative_first_part(path_value, root) == "fable-disk"


def bypass_enabled(payload: Dict[str, Any]) -> bool:
    return os.environ.get("PACK_BYPASS") == "1" or os.environ.get("FABLE_PACK_BYPASS") == "1"


def record_bypass(root: Path, payload: Dict[str, Any], reason: str) -> None:
    task_path = active_task_path(root)
    if not task_path:
        return
    meta_path = task_path / "meta.yaml"
    if not meta_path.exists():
        return
    meta = tracelib.load_yaml(meta_path)
    meta.setdefault("bypass_events", []).append(
        {
            "ts": tracelib.utc_now(),
            "reason": reason,
            "command": json.dumps({"tool": tool_name(payload), "input": tool_input(payload)}, ensure_ascii=True)[:1000],
        }
    )
    tracelib.write_yaml(meta_path, meta)


def should_run(payload: Dict[str, Any]) -> bool:
    return tracelib.should_record(payload)


def block(message: str) -> None:
    print("fable-pack BLOCK: " + message, file=sys.stderr)
    raise SystemExit(2)


def warn(message: str) -> None:
    print("fable-pack WARN: " + message, file=sys.stderr)
