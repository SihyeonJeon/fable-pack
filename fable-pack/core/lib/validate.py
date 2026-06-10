from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import tracelib

RULES_ROOT = Path(__file__).resolve().parents[1] / "rules"

GENERIC_VERIFICATION_PATTERNS = [
    "동작 확인",
    "잘 되는지 확인",
    "테스트 필요",
    "수동 검증",
    "확인 예정",
    "works",
    "check manually",
    "manual verification",
    "verify it works",
]


def verification_phrases() -> List[str]:
    """Load blocked phrases from rules YAML so rules files stay the source of truth."""
    rules_path = RULES_ROOT / "forbidden_generic_phrases.yaml"
    if rules_path.exists():
        try:
            data = tracelib.load_yaml(rules_path)
            phrases = data.get("verification_phrases")
            if isinstance(phrases, list) and phrases:
                return [str(p) for p in phrases]
        except Exception:
            pass
    return GENERIC_VERIFICATION_PATTERNS

STANDARD_DECISIONS = {
    "task_classification",
    "context_selection",
    "requirement_inference",
    "rejected_alternative",
    "acceptance_evidence_selection",
}

HEAVY_DECISIONS = STANDARD_DECISIONS | {
    "architecture_boundary",
    "risk_escalation",
    "non_goal_boundary",
    "worker_contract_boundary",
    "verifier_gate_boundary",
    "rollback_boundary",
    "shadow_delta_interpretation",
    "counterfactual_boundary",
}


@dataclass
class ValidationResult:
    ok: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def extend(self, other: "ValidationResult") -> None:
        self.ok = self.ok and other.ok
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def validate_task(task_id: Optional[str] = None, root: Optional[Path] = None, gate: str = "all") -> ValidationResult:
    root = root or tracelib.project_root()
    task_path = tracelib.task_dir(task_id, root)
    result = ValidationResult()
    if gate in ("all", "spec"):
        result.extend(spec_gate(task_path, root))
    if gate in ("all", "context"):
        result.extend(context_gate(task_path, root))
    if gate in ("all", "plan"):
        result.extend(plan_gate(task_path))
    if gate in ("all", "done"):
        result.extend(done_gate(task_path, root))
    if gate in ("all", "corpus"):
        result.extend(corpus_quality_gate(task_path))
    return result


def spec_gate(task_path: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    meta = required_yaml(task_path / "meta.yaml", result)
    grade = meta.get("grade", "STANDARD")
    if grade == "LIGHT":
        return result

    spec = required_yaml(task_path / "task_spec" / "final.yaml", result)
    context_pack = required_yaml(task_path / "context_pack.yaml", result)
    decisions = required_jsonl(task_path / "decision_events.jsonl", result)
    required_file(task_path / "observation_log.jsonl", result)
    if not result.ok:
        return result

    must_read = context_pack.get("must_read") or spec.get("repo_context", {}).get("must_read") or []
    if not must_read:
        result.fail("spec_gate: context_pack.must_read is empty.")
    for idx, item in enumerate(must_read):
        if isinstance(item, dict) and not item.get("selected_by_decision_ref"):
            result.fail(f"spec_gate: must_read[{idx}] missing selected_by_decision_ref: {item.get('path')}")
        elif isinstance(item, str):
            result.warn(f"spec_gate: must_read[{idx}] is a bare path without selected_by_decision_ref: {item}")
    if not context_pack.get("similar_implementations") and not context_pack.get("no_precedent_justification"):
        result.fail("spec_gate: similar_implementations is empty and no_precedent_justification is absent.")
    repo_context = spec.get("repo_context", {})
    if not repo_context.get("architectural_constraints"):
        result.fail("spec_gate: repo_context.architectural_constraints is empty.")

    rejected = spec.get("rejected_alternatives") or []
    min_rejected = 3 if grade == "HEAVY" else 2
    if len(rejected) < min_rejected:
        result.fail(f"spec_gate: rejected_alternatives requires at least {min_rejected} entries for {grade}.")
    if grade == "HEAVY":
        categories = {item.get("category") for item in rejected}
        for needed in ["tempting_shortcut", "architecture_alternative", "scope_boundary_alternative"]:
            if needed not in categories:
                result.fail(f"spec_gate: HEAVY rejected_alternatives missing category {needed}.")

    for risk in spec.get("risk_register") or []:
        if risk.get("severity") in ("high", "blocking") and not risk.get("mitigation"):
            result.fail(f"spec_gate: high/blocking risk lacks mitigation: {risk.get('risk')}")

    for assumption in spec.get("assumptions") or []:
        if assumption.get("blocking") and assumption.get("confidence") == "low":
            result.fail(f"spec_gate: blocking low-confidence assumption unresolved: {assumption.get('assumption')}")

    criteria = spec.get("acceptance_criteria") or []
    if not criteria:
        result.fail("spec_gate: acceptance_criteria is empty.")
    for criterion in criteria:
        verification = criterion.get("verification") or {}
        value = str(verification.get("value") or "")
        if not verification.get("type") or not value.strip():
            result.fail(f"spec_gate: acceptance criterion lacks concrete verification: {criterion.get('criterion')}")
        if contains_generic_phrase(value):
            result.fail(f"spec_gate: generic verification phrase is blocked: {value}")

    # Unfilled TODO skeletons (scaffolded at task start) never satisfy gates.
    filled_decisions = [event for event in decisions if event.get("status") != "todo"]
    decision_types = {event.get("event_type") for event in filled_decisions}
    required_types = HEAVY_DECISIONS if grade == "HEAVY" else STANDARD_DECISIONS
    missing = sorted(required_types - decision_types)
    if missing:
        result.fail("spec_gate: missing decision event types: " + ", ".join(missing))
    for event in filled_decisions:
        if event.get("decision") and not event.get("artifact_updates"):
            result.fail(f"spec_gate: decision seq={event.get('seq')} lacks artifact_updates.")
        for rejected_option in event.get("rejected_options") or []:
            if not rejected_option.get("category"):
                result.fail(f"spec_gate: decision seq={event.get('seq')} rejected option lacks category.")

    validate_grounded_refs(spec, task_path, result)
    return result


def context_gate(task_path: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    meta = required_yaml(task_path / "meta.yaml", result)
    grade = meta.get("grade", "STANDARD")
    if grade == "LIGHT":
        return result
    context_pack = required_yaml(task_path / "context_pack.yaml", result)
    context_events = required_jsonl(task_path / "context_log.jsonl", result)
    observations = required_jsonl(task_path / "observation_log.jsonl", result)
    if not result.ok:
        return result

    read_paths = {normalize_path(event.get("path", ""), root) for event in context_events}
    must_read_paths = [normalize_path(item.get("path", item), root) for item in context_pack.get("must_read", [])]
    for path in must_read_paths:
        if path not in read_paths:
            result.fail(f"context_gate: must_read path has no context_log event: {path}")

    # Auto-generated placeholders prove nothing was actually extracted from the
    # read; only filled observations may satisfy the gate.
    filled_observations = [event for event in observations if event.get("status") != "placeholder"]
    observed_paths = {normalize_path(event.get("path", ""), root) for event in filled_observations}
    for path in must_read_paths:
        if grade == "HEAVY" and path not in observed_paths:
            result.fail(f"context_gate: HEAVY must_read path lacks filled observation: {path}")
        elif path not in observed_paths:
            result.warn(f"context_gate: must_read path lacks filled observation: {path}")
    if grade == "HEAVY" and not any(event.get("changed_task_understanding") is True for event in filled_observations):
        result.fail("context_gate: HEAVY requires at least one changed_task_understanding observation.")
    return result


def plan_gate(task_path: Path) -> ValidationResult:
    result = ValidationResult()
    meta = required_yaml(task_path / "meta.yaml", result)
    if meta.get("grade") != "HEAVY":
        return result
    plan_path = task_path / "plan_graph.json"
    if not plan_path.exists():
        result.fail("plan_gate: HEAVY requires plan_graph.json.")
    else:
        plan = required_yaml(plan_path, result)
        nodes = plan.get("nodes") or []
        for idx, node in enumerate(nodes):
            if isinstance(node, dict) and not node.get("acceptance_signal"):
                result.fail(f"plan_gate: plan node missing acceptance_signal: nodes[{idx}] id={node.get('id')}")
    contracts = sorted((task_path / "worker_contracts").glob("*.yaml"))
    if not contracts:
        result.fail("plan_gate: HEAVY requires at least one worker_contracts/*.yaml.")
    for contract_path in contracts:
        contract = required_yaml(contract_path, result)
        body = contract.get("worker_contract", contract)
        if not isinstance(body, dict):
            continue
        scope = body.get("scope", body)
        if not (scope.get("allowed_files") or body.get("allowed_files")):
            result.fail(f"plan_gate: worker contract missing allowed_files: {contract_path.name}")
        if not (scope.get("forbidden_files") or body.get("forbidden_files")):
            result.fail(f"plan_gate: worker contract missing forbidden_files: {contract_path.name}")
    return result


def done_gate(task_path: Path, root: Path) -> ValidationResult:
    result = ValidationResult()
    meta = required_yaml(task_path / "meta.yaml", result)
    grade = meta.get("grade", "STANDARD")
    if grade == "LIGHT":
        return result
    spec = required_yaml(task_path / "task_spec" / "final.yaml", result)
    report = required_yaml(task_path / "verifier_report.yaml", result)
    required_file(task_path / "handoff.md", result)
    if not result.ok:
        return result

    criteria = spec.get("acceptance_criteria") or []
    if not criteria:
        result.fail("done_gate: acceptance_criteria is empty; nothing can be verified.")
    evidence_by_criterion = {item.get("criterion"): item for item in report.get("acceptance_evidence") or []}
    for criterion in criteria:
        key = criterion.get("criterion")
        evidence = evidence_by_criterion.get(key)
        if not evidence:
            result.fail(f"done_gate: missing acceptance evidence for: {key}")
        elif evidence.get("status") == "not_tested":
            result.fail(f"done_gate: acceptance evidence is not_tested for: {key}")
    for risk in report.get("risk_coverage") or []:
        if risk.get("risk") and risk.get("covered") is False:
            result.fail(f"done_gate: risk is not covered: {risk.get('risk')}")
    if report.get("forbidden_file_check", {}).get("touched_forbidden_file"):
        result.fail("done_gate: forbidden file was touched.")
    for change in report.get("unplanned_changes") or []:
        if not change.get("has_decision_event"):
            result.fail(f"done_gate: unplanned change lacks decision event: {change.get('path')}")
    for command in report.get("test_commands") or []:
        if command.get("status") == "fail" and report.get("verdict") == "approve":
            result.fail(f"done_gate: failed test command with approve verdict: {command.get('command')}")
    if grade == "HEAVY":
        if not list((task_path / "shadow").glob("*/delta.yaml")):
            result.fail("done_gate: HEAVY requires shadow/<fallback-model-id>/delta.yaml.")
        if not list((task_path / "counterfactuals").glob("*.yaml")):
            result.fail("done_gate: HEAVY requires at least one counterfactual probe.")
    return result


def corpus_quality_gate(task_path: Path) -> ValidationResult:
    result = ValidationResult()
    meta = required_yaml(task_path / "meta.yaml", result)
    required_yaml(task_path / "input_snapshot.yaml", result)
    required_yaml(task_path / "repo_snapshot.yaml", result)
    if not result.ok:
        return result
    if meta.get("context_log_status") == "UNVERIFIED":
        result.fail("corpus_quality_gate: UNVERIFIED context_log cannot enter golden corpus.")
    if meta.get("bypass_events"):
        result.fail("corpus_quality_gate: bypassed trace cannot enter golden corpus.")
    grade = meta.get("grade", "STANDARD")
    if grade != "LIGHT":
        report = required_yaml(task_path / "verifier_report.yaml", result)
        if report.get("verdict") != "approve":
            result.fail(f"corpus_quality_gate: verifier verdict must be approve, got: {report.get('verdict')}")
        decisions = required_jsonl(task_path / "decision_events.jsonl", result)
        for event in decisions:
            if event.get("status") == "todo":
                continue
            if event.get("decision") and not event.get("artifact_updates"):
                result.fail(f"corpus_quality_gate: decision seq={event.get('seq')} lacks artifact_updates.")
    if grade == "HEAVY":
        if not list((task_path / "shadow").glob("*/delta.yaml")):
            result.fail("corpus_quality_gate: HEAVY golden candidate requires a shadow delta.")
        if not list((task_path / "counterfactuals").glob("*.yaml")):
            result.fail("corpus_quality_gate: HEAVY golden candidate requires a counterfactual probe.")
    human = task_path / "human_review.yaml"
    if not human.exists():
        result.fail("corpus_quality_gate: human_review.yaml is required.")
    else:
        review = tracelib.load_yaml(human)
        if review.get("rating") in ("flawed", "rejected"):
            result.fail(f"corpus_quality_gate: human_review rating disallows golden corpus: {review.get('rating')}")
        if not review.get("rating"):
            result.fail("corpus_quality_gate: human_review rating is missing.")
    return result


def required_file(path: Path, result: ValidationResult) -> None:
    if not path.exists():
        result.fail(f"missing required artifact: {path}")


def required_yaml(path: Path, result: ValidationResult) -> Dict[str, Any]:
    if not path.exists():
        result.fail(f"missing required artifact: {path}")
        return {}
    try:
        return tracelib.load_yaml(path)
    except Exception as exc:
        result.fail(f"invalid YAML/JSON artifact {path}: {exc}")
        return {}


def required_jsonl(path: Path, result: ValidationResult) -> List[Dict[str, Any]]:
    if not path.exists():
        result.fail(f"missing required artifact: {path}")
        return []
    try:
        return tracelib.read_jsonl(path)
    except Exception as exc:
        result.fail(f"invalid JSONL artifact {path}: {exc}")
        return []


def contains_generic_phrase(value: str) -> bool:
    lowered = value.lower()
    for pattern in verification_phrases():
        lowered_pattern = pattern.lower()
        if lowered_pattern.isascii():
            # Word-boundary match so "works" does not flag "networks" or "frameworks".
            if re.search(r"\b" + re.escape(lowered_pattern) + r"\b", lowered):
                return True
        elif lowered_pattern in lowered:
            return True
    return False


def normalize_path(value: Any, root: Optional[Path] = None) -> str:
    if isinstance(value, dict):
        value = value.get("path", "")
    text = str(value or "").strip()
    # Hooks record absolute tool paths while authors write repo-relative
    # must_read entries; compare both in repo-relative form.
    if root is not None and text.startswith("/"):
        try:
            text = str(Path(text).resolve().relative_to(Path(root).resolve()))
        except ValueError:
            pass
    return text.lstrip("./")


def validate_grounded_refs(spec: Dict[str, Any], task_path: Path, result: ValidationResult) -> None:
    valid_prefixes = {
        "context_log",
        "observation_log",
        "decision_events",
        "command_log",
        "edit_log",
        "repo_snapshot",
        "input_snapshot",
    }

    def check_ref(ref: Any, location: str) -> None:
        if ref in (None, "", []):
            result.fail(f"spec_gate: missing evidence_ref at {location}.")
            return
        if isinstance(ref, list):
            for idx, item in enumerate(ref):
                check_ref(item, f"{location}[{idx}]")
            return
        text = str(ref)
        if ":" in text and text.split(":", 1)[0] in valid_prefixes:
            return
        if re.fullmatch(r"[0-9a-f]{7,40}", text):
            return
        project_root = task_path.parents[2] if len(task_path.parents) > 2 else task_path.parent
        candidate = project_root / text
        if candidate.exists():
            return
        result.warn(f"spec_gate: weak evidence reference at {location}: {text}")

    repo_context = spec.get("repo_context", {})
    for idx, item in enumerate(repo_context.get("architectural_constraints") or []):
        check_ref(item.get("evidence_ref"), f"repo_context.architectural_constraints[{idx}].evidence_ref")
    for section_name, items in (spec.get("inferred_requirements") or {}).items():
        for idx, item in enumerate(items or []):
            check_ref(item.get("evidence_ref"), f"inferred_requirements.{section_name}[{idx}].evidence_ref")
    for idx, item in enumerate(spec.get("risk_register") or []):
        check_ref(item.get("evidence_ref"), f"risk_register[{idx}].evidence_ref")
