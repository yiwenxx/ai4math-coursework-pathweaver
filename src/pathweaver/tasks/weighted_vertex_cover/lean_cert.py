"""Export independent Weighted Vertex Cover dual/optimality certificates to Lean 4."""
from collections.abc import Mapping
from typing import Any

from .evaluator import dual_packing_lower_bound, evaluate_prepared, prepare_verifier


def export_wvc_lean_certificate(
    raw_instance: Mapping[str, Any],
    solution: Mapping[str, Any],
    *,
    theorem_name: str | None = None,
) -> dict[str, Any]:
    """Recompute WVC cover validity & edge-packing duals and emit a Lean 4 proof."""
    prepared = prepare_verifier(raw_instance)
    instance = prepared.instance
    eval_result = evaluate_prepared(prepared, solution)
    if not eval_result.feasible or eval_result.objectives is None:
        raise ValueError(
            "Cannot export Lean certificate for infeasible WVC solution: "
            + "; ".join(eval_result.violations[:4])
        )

    dual_total, edge_duals = dual_packing_lower_bound(instance)
    total_weight = eval_result.objectives[0]
    is_optimal = total_weight == dual_total
    chosen_theorem = theorem_name or ("wvc_finite_optimal" if is_optimal else "wvc_certified_bound")

    v_index = {vid: idx for idx, vid in enumerate(instance.vertex_ids)}
    selected_set = set(solution["solution"]["selected_vertices"])
    weights_arr = "#[" + ", ".join(str(instance.weights[vid]) for vid in instance.vertex_ids) + "]"
    sel_arr = "#[" + ", ".join("true" if vid in selected_set else "false" for vid in instance.vertex_ids) + "]"
    edges_list = "[" + ", ".join(f"({v_index[u]}, {v_index[v]})" for u, v in instance.edges) + "]"
    duals_list = "[" + ", ".join(str(edge_duals.get(f"{u}-{v}", 0)) for u, v in instance.edges) + "]"

    if is_optimal:
        theorem_block = [
            f"theorem {chosen_theorem} :",
            "    IsValidCover wvcEdges (getBool wvcSel) ∧",
            "    (∀ sel', IsValidCover wvcEdges sel' →",
            "      coverWeight wvcWeights.size (getNat wvcWeights) (getBool wvcSel) ≤",
            "      coverWeight wvcWeights.size (getNat wvcWeights) sel') :=",
            "  verify_wvc_optimal_sound wvcWeights wvcEdges wvcDuals wvcSel",
            "    (by rfl) (by rfl) (by rfl) (by rfl) (by rfl)",
        ]
    else:
        theorem_block = [
            f"theorem {chosen_theorem} :",
            "    IsValidCover wvcEdges (getBool wvcSel) ∧",
            "    (∀ sel', IsValidCover wvcEdges sel' → sumList wvcDuals ≤ coverWeight wvcWeights.size (getNat wvcWeights) sel') ∧",
            "    sumList wvcDuals ≤ coverWeight wvcWeights.size (getNat wvcWeights) (getBool wvcSel) :=",
            "  verify_wvc_dual_bound_sound wvcWeights wvcEdges wvcDuals wvcSel",
            "    (by rfl) (by rfl) (by rfl) (by rfl)",
        ]

    lean_source = "\n".join([
        "import PathWeaverFormal.WvcDuality",
        "",
        f"-- Instance: {instance.instance_id}",
        f"-- Total weight = {total_weight}, Dual packing lower bound = {dual_total}",
        "open PathWeaverFormal.Wvc",
        "",
        f"def wvcWeights : Array Nat := {weights_arr}",
        f"def wvcEdges : List (Nat × Nat) := {edges_list}",
        f"def wvcDuals : List Nat := {duals_list}",
        f"def wvcSel : Array Bool := {sel_arr}",
        "",
        *theorem_block,
        "",
        f"#print axioms {chosen_theorem}",
        "",
    ])
    return {
        "instance_id": instance.instance_id,
        "theorem_name": chosen_theorem,
        "certificate_kind": "wvc_finite_optimal_lean" if is_optimal else "wvc_dual_bound_lean",
        "total_weight": total_weight,
        "dual_lower_bound": dual_total,
        "lean_source": lean_source,
    }
