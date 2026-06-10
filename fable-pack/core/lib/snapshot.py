from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import tracelib


def refresh_repo_snapshot(task_id: str | None = None, root: Path | None = None) -> Dict[str, Any]:
    root = root or tracelib.project_root()
    task_path = tracelib.task_dir(task_id, root)
    repo = tracelib.repo_state(root)
    existing = {}
    snapshot_path = task_path / "repo_snapshot.yaml"
    if snapshot_path.exists():
        existing = tracelib.load_yaml(snapshot_path)
    snapshot = {
        "commit": repo["commit"],
        "branch": repo["branch"],
        "status": repo["status"],
        "diff_hash_before": existing.get("diff_hash_before", repo["diff_hash_before"]),
        "diff_hash_after": repo["diff_hash_before"],
        "important_paths": existing.get("important_paths", []),
        "lockfiles": tracelib.list_lockfiles(root),
    }
    tracelib.write_yaml(snapshot_path, snapshot)
    return snapshot


def freeze_task(task_id: str | None = None, root: Path | None = None) -> Dict[str, Any]:
    root = root or tracelib.project_root()
    task_path = tracelib.task_dir(task_id, root)
    snapshot = refresh_repo_snapshot(task_id, root)
    manifest = {
        "task_id": task_path.name,
        "frozen_at": tracelib.utc_now(),
        "repo_snapshot": snapshot,
        "artifacts": [],
    }
    for path in sorted(task_path.rglob("*")):
        if path.is_file():
            manifest["artifacts"].append(
                {
                    "path": str(path.relative_to(task_path)),
                    "sha256": tracelib.sha256_file(path),
                }
            )
    tracelib.write_yaml(task_path / "freeze_manifest.yaml", manifest)
    return manifest
