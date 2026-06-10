from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import tracelib


COMPARISON_FIELDS = [
    ("task_classification", "task_classification"),
    ("architectural_constraints", "repo_context.architectural_constraints"),
    ("inferred_requirements", "inferred_requirements"),
    ("non_goals", "non_goals"),
    ("rejected_alternatives", "rejected_alternatives"),
    ("risk_register", "risk_register"),
    ("acceptance_criteria", "acceptance_criteria"),
]


def scaffold_shadow(base_task_id: str, comparison_model_id: str, root: Path | None = None) -> Path:
    """Create the comparison-trace pair structure so the second trace has a
    ready slot: copied input/repo snapshots plus empty artifact templates.
    Returns the comparison trace directory (shadow/<model-id>/trace/)."""
    root = root or tracelib.project_root()
    base_path = tracelib.task_dir(base_task_id, root)
    shadow_dir = base_path / "shadow" / comparison_model_id
    trace_dir = shadow_dir / "trace"
    (trace_dir / "task_spec").mkdir(parents=True, exist_ok=True)
    for name in ["input_snapshot.yaml", "repo_snapshot.yaml"]:
        source = base_path / name
        if source.exists():
            (trace_dir / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    spec_path = trace_dir / "task_spec" / "final.yaml"
    if not spec_path.exists():
        base_spec = tracelib.load_yaml(base_path / "task_spec" / "final.yaml")
        tracelib.write_yaml(spec_path, tracelib.empty_task_spec(
            base_task_id + "-shadow",
            str(base_spec.get("user_goal") or ""),
            str((base_spec.get("task_classification") or {}).get("primary_type") or "general"),
        ))
    (trace_dir / "decision_events.jsonl").touch(exist_ok=True)
    critiques = shadow_dir / "critiques.yaml"
    if not critiques.exists():
        tracelib.write_yaml(critiques, {
            "base_task_id": base_task_id,
            "comparison_model_id": comparison_model_id,
            "critiques": [],
            "instructions": "After the comparison trace reaches PLAN, list concrete gaps here, then run `pack shadow run` to compute delta.yaml.",
        })
    return trace_dir


def make_shadow_delta(
    base_task_id: str,
    fallback_model_id: str,
    fallback_trace_ref: str,
    root: Path | None = None,
) -> Dict[str, Any]:
    root = root or tracelib.project_root()
    base_path = tracelib.task_dir(base_task_id, root)
    fallback_path = Path(fallback_trace_ref)
    if not fallback_path.is_absolute():
        fallback_path = root / fallback_trace_ref
    fable_spec = tracelib.load_yaml(base_path / "task_spec" / "final.yaml")
    fallback_spec = tracelib.load_yaml(fallback_path / "task_spec" / "final.yaml") if fallback_path.exists() else {}

    missed = []
    for category, dotted in COMPARISON_FIELDS:
        fable_value = get_dotted(fable_spec, dotted)
        fallback_value = get_dotted(fallback_spec, dotted)
        if has_content(fable_value) and not has_content(fallback_value):
            missed.append(
                {
                    "id": f"missed_{category}",
                    "category": taxonomy_for(category),
                    "fable_item": {"artifact": f"task_spec.final.{dotted}", "text": summarize(fable_value)},
                    "fallback_missing_or_weak_item": {"artifact": f"task_spec.final.{dotted}", "text": None},
                    "likely_failure": [f"Fallback may proceed without {category} boundary."],
                    "severity": "high" if category in ("architectural_constraints", "risk_register") else "medium",
                    "convert_to": {
                        "schema_field": f"task_spec.{dotted}",
                        "gate_rule": "spec_gate",
                        "playbook_rule": None,
                        "invariant": None,
                        "example": {"type": "good", "name": f"{base_task_id}_{category}"},
                    },
                }
            )
    delta = {
        "base_task_id": base_task_id,
        "fable_trace_ref": str(base_path),
        "fallback_model_id": fallback_model_id,
        "fallback_trace_ref": str(fallback_path),
        "missed_by_fallback": missed,
        "stronger_in_fallback": [],
        "summary": {
            "critical_omission_count": sum(1 for item in missed if item.get("severity") == "blocking"),
            "rule_patches_required": len(missed),
        },
    }
    out = base_path / "shadow" / fallback_model_id / "delta.yaml"
    tracelib.write_yaml(out, delta)
    tracelib.write_yaml(base_path / "shadow" / fallback_model_id / "omission_to_rule_patch.yaml", omission_to_rule_patch(delta))
    return delta


def omission_to_rule_patch(delta: Dict[str, Any]) -> Dict[str, Any]:
    patches = []
    for item in delta.get("missed_by_fallback") or []:
        convert_to = item.get("convert_to") or {}
        if convert_to.get("gate_rule"):
            patches.append(
                {
                    "rule_id": f"shadow_{item.get('id')}",
                    "action": "add",
                    "condition": f"Fallback missing {item.get('category')}",
                    "block_message": item.get("likely_failure", ["Fallback omission"])[0],
                }
            )
    return {
        "task_id": delta.get("base_task_id"),
        "source": {"type": "shadow_delta", "ref": "shadow/delta.yaml"},
        "patches": {
            "schema": [],
            "gate_rules": patches,
            "playbook_rules": [],
            "examples": [],
            "invariants": [],
        },
    }


def get_dotted(data: Dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict, str)):
        return bool(value)
    return True


def summarize(value: Any) -> str:
    text = str(value)
    return text[:500] + ("...<truncated>" if len(text) > 500 else "")


def taxonomy_for(category: str) -> str:
    return {
        "architectural_constraints": "missed_architecture_constraint",
        "risk_register": "unsafe_assumption",
        "acceptance_criteria": "under_specified_acceptance",
        "non_goals": "ignored_non_goal",
        "rejected_alternatives": "poor_context_selection",
    }.get(category, "missed_existing_policy")
