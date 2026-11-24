"""Zero-cost L0 behavioral delta extraction and candidate attribution parsing."""
from collections.abc import Mapping, Sequence
import re
from typing import Any

from pathweaver.core.research_records import ResearchEvent, canonical_json
from pathweaver.research.strategy_escape import classify_algorithmic_regime


_HYP_REF_RE = re.compile(
    r"(?:#|--)\s*pathweaver-hypothesis:\s*([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})"
)
_LESSON_REF_RE = re.compile(
    r"(?:#|--)\s*pathweaver-lesson:\s*([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})"
)

_FAILURE_TAG_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("bottleneck", "bottleneck"),
    ("critical_path", "bottleneck"),
    ("hall", "capacity"),
    ("capacity", "capacity"),
    ("bound_gap", "lower_bound"),
    ("lower_bound", "lower_bound"),
    ("redundant", "redundant_prune"),
    ("uncovered", "uncovered_edge"),
    ("violating_progressions", "ap_conflict"),
    ("arithmetic progression", "ap_conflict"),
    ("unsolved goals", "lean_tactic_error"),
    ("type mismatch", "lean_tactic_error"),
    ("sorry", "lean_tactic_error"),
    ("timeout", "timeout"),
)


def extract_declared_references(source: str) -> dict[str, str | None]:
    """Parse optional hypothesis/lesson attribution headers from the first 40 lines."""
    if not isinstance(source, str) or not source:
        return {"hypothesis_id": None, "lesson_id": None}
    header = "\n".join(source.splitlines()[:40])
    hyp_match = _HYP_REF_RE.search(header)
    lesson_match = _LESSON_REF_RE.search(header)
    return {
        "hypothesis_id": hyp_match.group(1) if hyp_match else None,
        "lesson_id": lesson_match.group(1) if lesson_match else None,
    }


def compute_attempt_delta(
    source: str,
    *,
    language: str = "auto",
    outcome: str,
    objectives: Sequence[int] | None,
    evaluations: Sequence[Mapping[str, Any]],
    failure: str = "",
    parent_event: ResearchEvent | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Compute counterfactual parent-child delta, bottleneck signatures, and signal tier."""
    regime = classify_algorithmic_regime(source, language=language)
    per_instance_objectives: dict[str, list[int]] = {}
    per_instance_gaps: dict[str, int] = {}
    invalid_instances: list[str] = []

    for row in evaluations:
        if not isinstance(row, Mapping):
            continue
        inst_id = row.get("instance_id")
        if not isinstance(inst_id, str) or not inst_id.strip():
            continue
        ev = row.get("evaluation") if isinstance(row.get("evaluation"), Mapping) else row
        if ev.get("feasible") is True:
            objs = ev.get("objectives")
            if isinstance(objs, (list, tuple)) and objs:
                vec = [int(v) for v in objs]
                per_instance_objectives[inst_id] = vec
                lb = ev.get("lower_bound")
                if isinstance(lb, (list, tuple)) and lb:
                    per_instance_gaps[inst_id] = max(0, int(vec[0]) - int(lb[0]))
        elif ev.get("feasible") is False:
            invalid_instances.append(inst_id)

    total_bound_gap: int | None = None
    if per_instance_objectives and len(per_instance_gaps) == len(per_instance_objectives):
        total_bound_gap = sum(per_instance_gaps.values())

    if outcome == "feasible" and per_instance_objectives:
        if any(gap > 0 for gap in per_instance_gaps.values()):
            bottleneck_instances = sorted(
                (iid for iid, gap in per_instance_gaps.items() if gap > 0),
                key=lambda iid: (-per_instance_gaps[iid], -per_instance_objectives[iid][0], iid),
            )[:3]
        else:
            bottleneck_instances = sorted(
                per_instance_objectives,
                key=lambda iid: (-per_instance_objectives[iid][0], iid),
            )[:3]
    elif outcome == "invalid":
        if invalid_instances:
            bottleneck_instances = list(dict.fromkeys(invalid_instances))[:3]
        elif ":" in failure:
            prefix = failure.split(":", 1)[0].strip()
            bottleneck_instances = [prefix] if prefix else []
        else:
            bottleneck_instances = []
    else:
        bottleneck_instances = []

    parent_objs: list[int] | None = None
    parent_regime: str | None = None
    parent_gap: int | None = None
    improved_instances: list[str] = []
    regressed_instances: list[str] = []
    objective_delta: list[int] | None = None
    bound_gap_delta: int | None = None

    if parent_event is not None and parent_event.kind == "attempt":
        p_payload = parent_event.payload
        p_objs = p_payload.get("objectives")
        if isinstance(p_objs, (list, tuple)) and p_objs:
            parent_objs = [int(v) for v in p_objs]
        p_delta = (p_payload.get("diagnostics") or {}).get("delta") or {}
        if isinstance(p_delta, Mapping):
            raw_p_regime = p_delta.get("regime")
            if isinstance(raw_p_regime, str) and raw_p_regime.strip():
                parent_regime = raw_p_regime
            if isinstance(p_delta.get("total_bound_gap"), int):
                parent_gap = p_delta["total_bound_gap"]
            p_per_inst = p_delta.get("per_instance_objectives")
            if isinstance(p_per_inst, Mapping) and per_instance_objectives:
                for iid in sorted(per_instance_objectives):
                    c_vec = per_instance_objectives[iid]
                    p_vec = p_per_inst.get(iid)
                    if isinstance(p_vec, (list, tuple)) and len(p_vec) == len(c_vec):
                        c_tuple = tuple(c_vec)
                        p_tuple = tuple(int(x) for x in p_vec)
                        if c_tuple < p_tuple:
                            improved_instances.append(iid)
                        elif c_tuple > p_tuple:
                            regressed_instances.append(iid)
        if (
            outcome == "feasible"
            and objectives is not None
            and parent_objs is not None
            and len(objectives) == len(parent_objs)
        ):
            objective_delta = [int(c) - int(p) for c, p in zip(objectives, parent_objs)]
        if total_bound_gap is not None and parent_gap is not None:
            bound_gap_delta = total_bound_gap - parent_gap

    regime_transition = f"{parent_regime}->{regime}" if parent_regime else regime

    if outcome == "pruned_dominated":
        signal_tier = "dominated_pruned"
    elif outcome in {"malformed", "timeout", "exception"}:
        signal_tier = "execution_noise"
    elif (
        outcome == "feasible"
        and objectives is not None
        and parent_objs is not None
        and tuple(int(v) for v in objectives) < tuple(parent_objs)
    ):
        signal_tier = "breakthrough"
    elif (
        outcome == "feasible"
        and objectives is not None
        and (
            bool(improved_instances)
            or (
                parent_objs is not None
                and len(objectives) >= 2
                and len(objectives) == len(parent_objs)
                and any(int(objectives[i]) < int(parent_objs[i]) for i in range(1, len(objectives)))
            )
        )
    ):
        signal_tier = "stepping_stone"
    elif outcome == "invalid" or (
        outcome == "feasible"
        and ((total_bound_gap is not None and total_bound_gap > 0) or parent_objs is not None)
    ):
        signal_tier = "structural_obstruction"
    else:
        signal_tier = "baseline_feasible"

    tags: list[str] = [f"regime:{regime}", f"signal:{signal_tier}"]
    for iid in improved_instances[:4]:
        tags.append(f"win_inst:{iid}")
        if signal_tier == "stepping_stone":
            tags.append(f"stepping_stone_on:{iid}")
    for iid in bottleneck_instances[:3]:
        tags.append(f"bottleneck_inst:{iid}")

    diag_blob_parts = [failure.lower()]
    for row in evaluations[:6]:
        if isinstance(row, Mapping):
            ev = row.get("evaluation") if isinstance(row.get("evaluation"), Mapping) else row
            diag = ev.get("diagnostics")
            if isinstance(diag, Mapping) and diag:
                try:
                    diag_blob_parts.append(canonical_json(diag)[:400].lower())
                except Exception:
                    pass
    diag_blob = " ".join(diag_blob_parts)
    for needle, tag in _FAILURE_TAG_KEYWORDS:
        if needle in diag_blob:
            tags.append(tag)

    dedup_tags = list(dict.fromkeys(tag for tag in tags if isinstance(tag, str) and tag.strip()))
    delta_info: dict[str, Any] = {
        "regime": regime,
        "parent_regime": parent_regime,
        "regime_transition": regime_transition,
        "signal_tier": signal_tier,
        "objective_delta": objective_delta,
        "total_bound_gap": total_bound_gap,
        "bound_gap_delta": bound_gap_delta,
        "per_instance_objectives": per_instance_objectives,
        "per_instance_gaps": per_instance_gaps,
        "improved_instances": improved_instances,
        "regressed_instances": regressed_instances,
        "bottleneck_instances": bottleneck_instances,
    }
    return delta_info, dedup_tags
