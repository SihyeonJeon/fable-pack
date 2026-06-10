from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import sys

PACK_ROOT = Path(__file__).resolve().parents[2]
LIB_ROOT = PACK_ROOT / "core" / "lib"
sys.path.insert(0, str(LIB_ROOT))

import validate  # noqa: E402


def register_gates(harness: Any, project_root: str | Path) -> None:
    """Register fable-pack gates with a harness exposing `add_gate`."""

    root = Path(project_root)
    harness.add_gate("SPEC", "IMPLEMENT", lambda task_id: require_ok(validate.validate_task(task_id, root, "spec")))
    harness.add_gate("CONTEXT", "IMPLEMENT", lambda task_id: require_ok(validate.validate_task(task_id, root, "context")))
    harness.add_gate("PLAN", "IMPLEMENT", lambda task_id: require_ok(validate.validate_task(task_id, root, "plan")))
    harness.add_gate("VERIFY", "DONE", lambda task_id: require_ok(validate.validate_task(task_id, root, "done")))


def require_ok(result: validate.ValidationResult) -> Dict[str, Any]:
    return {"ok": result.ok, "errors": result.errors, "warnings": result.warnings}
