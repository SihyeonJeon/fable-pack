from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import tracelib
import validate

GOLDEN_RATINGS = {"exemplary", "normal"}
FLAWED_RATINGS = {"flawed"}


def promote(task_id: str, root: Path | None = None) -> Dict[str, Any]:
    """Promote a closed trace into the corpus.

    Rating exemplary/normal -> corpus/fable_golden (corpus_quality_gate must pass).
    Rating flawed -> corpus/flawed_examples (kept as negative example).
    Rating rejected/missing -> refused.
    """
    root = root or tracelib.project_root()
    task_path = tracelib.task_dir(task_id, root)
    review = tracelib.load_yaml(task_path / "human_review.yaml") if (task_path / "human_review.yaml").exists() else {}
    rating = str(review.get("rating") or "")
    if rating in GOLDEN_RATINGS:
        gate = validate.corpus_quality_gate(task_path)
        if not gate.ok:
            raise ValueError("corpus_quality_gate failed: " + "; ".join(gate.errors))
        bucket = "fable_golden"
    elif rating in FLAWED_RATINGS:
        bucket = "flawed_examples"
    else:
        raise ValueError(
            f"human_review.rating={rating or 'missing'} is not promotable. "
            "Set rating to exemplary/normal (golden) or flawed (negative example) first."
        )

    tracelib.ensure_disk(root)
    dest = tracelib.corpus_root(root) / bucket / task_path.name
    if dest.exists():
        raise ValueError(f"corpus entry already exists: {dest}")
    shutil.copytree(task_path, dest)

    meta = tracelib.load_yaml(task_path / "meta.yaml")
    entry = {
        "task_id": task_path.name,
        "bucket": bucket,
        "rating": rating,
        "grade": meta.get("grade"),
        "task_type": meta.get("task_type"),
        "model_id": (meta.get("model") or {}).get("model_id"),
        "promoted_at": tracelib.utc_now(),
        "source_trace": str(task_path),
        "corpus_path": str(dest),
    }
    tracelib.append_jsonl(tracelib.corpus_root(root) / "index.jsonl", entry)
    return entry


def iter_tasks(root: Path | None = None) -> List[Path]:
    root = root or tracelib.project_root()
    trace = tracelib.trace_root(root)
    if not trace.exists():
        return []
    return [path for path in sorted(trace.iterdir()) if path.is_dir()]


def coverage(root: Path | None = None) -> Dict[str, Any]:
    tasks = iter_tasks(root)
    grade_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    rating_counts: Counter[str] = Counter()
    human_counts: Counter[str] = Counter()
    shadow_by_type: Counter[str] = Counter()
    counterfactual_by_type: Counter[str] = Counter()
    missing_heavy: Dict[str, List[str]] = {}
    rejected_categories: Counter[str] = Counter()

    for task in tasks:
        meta_path = task / "meta.yaml"
        if not meta_path.exists():
            continue
        meta = tracelib.load_yaml(meta_path)
        grade = meta.get("grade", "UNKNOWN")
        task_type = meta.get("task_type", "unknown")
        grade_counts[grade] += 1
        type_counts[task_type] += 1
        if meta.get("golden_rating"):
            rating_counts[str(meta.get("golden_rating"))] += 1
        human_counts[str(meta.get("human_label_status", "unknown"))] += 1
        if list((task / "shadow").glob("*/delta.yaml")):
            shadow_by_type[task_type] += 1
        if list((task / "counterfactuals").glob("*.yaml")):
            counterfactual_by_type[task_type] += 1
        spec_path = task / "task_spec" / "final.yaml"
        if spec_path.exists():
            spec = tracelib.load_yaml(spec_path)
            for item in spec.get("rejected_alternatives") or []:
                rejected_categories[str(item.get("category", "unknown"))] += 1
        if grade == "HEAVY":
            missing = []
            for rel in [
                "plan_graph.json",
                "self_review.yaml",
                "human_review.yaml",
                "distillation_patch.yaml",
            ]:
                if not (task / rel).exists():
                    missing.append(rel)
            if not list((task / "shadow").glob("*/delta.yaml")):
                missing.append("shadow/<fallback-model-id>/delta.yaml")
            if not list((task / "counterfactuals").glob("*.yaml")):
                missing.append("counterfactuals/*.yaml")
            if missing:
                missing_heavy[task.name] = missing

    return {
        "task_count": len(tasks),
        "grade_counts": dict(grade_counts),
        "task_type_counts": dict(type_counts),
        "task_type_shadow_counts": dict(shadow_by_type),
        "task_type_counterfactual_counts": dict(counterfactual_by_type),
        "golden_rating_counts": dict(rating_counts),
        "human_review_status_counts": dict(human_counts),
        "rejected_alternative_category_counts": dict(rejected_categories),
        "heavy_missing_artifacts": missing_heavy,
    }


def markdown_report(root: Path | None = None) -> str:
    data = coverage(root)
    lines = ["# fable-pack corpus coverage", ""]
    lines.append(f"- total_traces: {data['task_count']}")
    for key in [
        "grade_counts",
        "task_type_counts",
        "task_type_shadow_counts",
        "task_type_counterfactual_counts",
        "golden_rating_counts",
        "human_review_status_counts",
        "rejected_alternative_category_counts",
    ]:
        lines.append(f"- {key}: {data[key]}")
    if data["heavy_missing_artifacts"]:
        lines.append("")
        lines.append("## HEAVY traces missing artifacts")
        for task_id, missing in data["heavy_missing_artifacts"].items():
            lines.append(f"- {task_id}: {', '.join(missing)}")
    return "\n".join(lines) + "\n"
