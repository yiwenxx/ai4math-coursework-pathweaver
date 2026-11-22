"""Independent verification, dual packing lower bound, compiled cache, and generalized certificates for WVC."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pathweaver.core.contracts import Evaluation, EvidenceLevel, validate_solution_envelope
from .certificate import check_certificate
from .model import Instance, SCHEMA_VERSION, TASK_ID, parse_instance


def dual_packing_lower_bound(instance: Instance) -> tuple[int, dict[str, int]]:
    """Compute a sound integer edge-packing dual lower bound.

    Assign nonnegative integer duals y_e >= 0 to edges such that for every vertex v,
    sum_{e incident to v} y_e <= weight(v). By weak LP duality, sum_e y_e <= OPT.
    """
    residual = dict(instance.weights)
    dual_total = 0
    edge_duals: dict[str, int] = {}
    ordered = sorted(
        instance.edges,
        key=lambda e: (min(residual[e[0]], residual[e[1]]), residual[e[0]] + residual[e[1]], e),
    )
    for u, v in ordered:
        slack = min(residual[u], residual[v])
        if slack > 0:
            residual[u] -= slack
            residual[v] -= slack
            dual_total += slack
            edge_duals[f"{u}-{v}"] = slack
    return dual_total, edge_duals


@dataclass(frozen=True)
class PreparedWvcInstance:
    instance: Instance
    base_lower_bound: int


def prepare_verifier(raw_instance: Mapping[str, Any]) -> PreparedWvcInstance:
    instance = parse_instance(raw_instance)
    lb_val, _ = dual_packing_lower_bound(instance)
    return PreparedWvcInstance(instance=instance, base_lower_bound=lb_val)


def evaluate_prepared(prepared: PreparedWvcInstance, solution: Any) -> Evaluation:
    instance = prepared.instance
    lower_bound_val = prepared.base_lower_bound
    lower_bound = (lower_bound_val,)

    payload, violations = validate_solution_envelope(
        solution, task_id=TASK_ID, instance_id=instance.instance_id, schema_version=SCHEMA_VERSION,
    )
    if payload is None:
        return Evaluation(False, None, tuple(violations), lower_bound=lower_bound)
    raw_selected = payload.get("selected_vertices")
    if not isinstance(raw_selected, Sequence) or isinstance(raw_selected, (str, bytes)):
        return Evaluation(
            False, None, (*violations, "solution.selected_vertices must be an array of vertex IDs"),
            lower_bound=lower_bound,
        )

    selected_set: set[str] = set()
    for idx, vid in enumerate(raw_selected):
        if not isinstance(vid, str) or vid not in instance.weights:
            violations.append(f"selected_vertices[{idx}] references unknown vertex {vid!r}")
            continue
        if vid in selected_set:
            violations.append(f"duplicate vertex {vid!r} in selected_vertices")
            continue
        selected_set.add(vid)

    uncovered = [[u, v] for u, v in instance.edges if u not in selected_set and v not in selected_set]
    if uncovered:
        violations.append(f"{len(uncovered)} edge(s) uncovered, first: {uncovered[0]}")

    redundant = sorted(
        vid for vid in selected_set
        if all(neighbor in selected_set for neighbor in instance.adjacency[vid])
    )
    expensive = sorted(selected_set, key=lambda vid: (-instance.weights[vid], vid))[:5]

    if violations:
        return Evaluation(
            feasible=False,
            objectives=None,
            violations=tuple(violations),
            diagnostics={
                "vertex_count": len(instance.vertex_ids),
                "edge_count": len(instance.edges),
                "selected_count": len(selected_set),
                "uncovered_count": len(uncovered),
                "uncovered_edges": uncovered[:5],
                "redundant_vertices": redundant[:5],
            },
            lower_bound=lower_bound,
            evidence=EvidenceLevel.EXPERIMENTAL,
        )

    total_weight = sum(instance.weights[vid] for vid in selected_set)
    cert_result = check_certificate(
        instance,
        solution.get("optimality_certificate"),
        total_weight=total_weight,
        base_lower_bound=lower_bound_val,
    )
    effective_lb = lower_bound_val
    if cert_result["status"] == "verified":
        effective_lb = max(effective_lb, int(cert_result["certified_lower_bound"]))

    if total_weight == effective_lb:
        evidence = EvidenceLevel.FINITE_OPTIMAL
    elif cert_result["status"] == "verified" and cert_result.get("evidence") == EvidenceLevel.CERTIFIED_BOUND.value:
        evidence = EvidenceLevel.CERTIFIED_BOUND
    else:
        evidence = EvidenceLevel.EXPERIMENTAL

    return Evaluation(
        feasible=True,
        objectives=(total_weight,),
        violations=(),
        diagnostics={
            "vertex_count": len(instance.vertex_ids),
            "edge_count": len(instance.edges),
            "selected_count": len(selected_set),
            "total_weight": total_weight,
            "dual_lower_bound": effective_lb,
            "base_edge_packing_bound": lower_bound_val,
            "bound_gap": total_weight - effective_lb,
            "redundant_vertices": redundant[:8],
            "redundant_weight": sum(instance.weights[v] for v in redundant),
            "expensive_choices": [{"id": v, "weight": instance.weights[v]} for v in expensive],
            "optimality_certificate": cert_result,
        },
        lower_bound=(effective_lb,),
        evidence=evidence,
    )


def evaluate(raw_instance: Mapping[str, Any], solution: Any) -> Evaluation:
    """Independently check membership, uniqueness, coverage and summed weight."""
    return evaluate_prepared(prepare_verifier(raw_instance), solution)
