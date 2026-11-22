"""Export independent EDA duality & Hall-conflict certificates to kernel-checked Lean 4 proofs."""
from collections.abc import Mapping
from typing import Any

from .evaluator import evaluate_prepared, prepare_verifier
from .model import geometric_length


def _lean_array_1d(items: list[str]) -> str:
    return "#[" + ", ".join(items) + "]"


def _lean_array_2d(rows: list[list[str]]) -> str:
    return "#[\n  " + ",\n  ".join(_lean_array_1d(row) for row in rows) + "\n]"


def _lean_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def export_eda_lean_certificate(
    raw_instance: Mapping[str, Any],
    solution: Mapping[str, Any],
    *,
    theorem_name: str = "eda_finite_optimal",
) -> dict[str, Any]:
    """Recompute EDA feasibility, Hall lower bounds, and duals to emit a Lean 4 proof."""
    prepared = prepare_verifier(raw_instance)
    instance = prepared.instance
    eval_result = evaluate_prepared(prepared, solution, include_edge_details=False)
    if not eval_result.feasible or eval_result.objectives is None or eval_result.lower_bound is None:
        raise ValueError(
            "Cannot export Lean certificate for infeasible EDA solution: "
            + "; ".join(eval_result.violations[:4])
        )

    cert_diag = eval_result.diagnostics.get("optimality_certificate") or {}
    cert_status = cert_diag.get("status")
    cert_method = cert_diag.get("method")
    attained = bool(eval_result.diagnostics.get("lower_bound_attained"))
    if cert_status != "verified" and not attained:
        raise ValueError(
            "EDA solution lacks a verified optimality_certificate and does not attain the independent lower bound"
        )

    assignment = dict(solution["solution"]["assignment"])
    forced = {
        edge.id: edge.eligible_sites[0]
        for edge in instance.cross_edges
        if len(edge.eligible_sites) == 1
    }
    reserved = set(forced.values())
    movable = [edge for edge in instance.cross_edges if edge.id not in forced]
    edge_index = {edge.id: idx for idx, edge in enumerate(movable)}
    sites = sorted({site for edge in movable for site in edge.eligible_sites if site not in reserved})
    site_index = {site_id: idx for idx, site_id in enumerate(sites)}

    relaxed_arrivals = prepared.relaxed_arrivals
    relaxed_remaining = prepared.relaxed_remaining
    t_bound = int(cert_diag["T_lower_bound"]) if cert_status == "verified" else eval_result.lower_bound[0]

    def _allowed_matrix(threshold: int) -> list[list[str]]:
        rows: list[list[str]] = []
        for edge in movable:
            cap = threshold - relaxed_arrivals[edge.source] - relaxed_remaining[edge.target]
            eligible_set = set(edge.eligible_sites)
            rows.append([
                "true" if (site_id in eligible_set and edge.base_delay + edge.alpha * geometric_length(instance, edge, site_id) <= cap)
                else "false"
                for site_id in sites
            ])
        return rows

    lengths_matrix = [
        [str(geometric_length(instance, edge, site_id)) for site_id in sites]
        for edge in movable
    ]
    allowed_matrix = _allowed_matrix(t_bound)
    assign_indices = [str(site_index[assignment[edge.id]]) for edge in movable]

    fixed_length = sum(
        geometric_length(instance, edge, forced[edge.id])
        for edge in instance.cross_edges
        if edge.id in forced
    )
    n_edges = len(movable)
    m_sites = len(sites)

    raw_cert = solution.get("optimality_certificate") or {}
    has_hall = cert_status == "verified" and cert_method in {"hall_bottleneck_and_dual", "hall_bottleneck_lower_bound"}
    has_dual = (cert_status == "verified" and cert_method in {"relaxed_path_matching_duality", "hall_bottleneck_and_dual"}) or attained

    lines = [
        "import PathWeaverFormal.EdaDuality",
        "",
        f"-- Instance: {instance.instance_id}",
        f"-- Certified T_lb = {t_bound}, total L = {eval_result.objectives[1]} (fixed = {fixed_length})",
        "open PathWeaverFormal.Eda",
        "",
        f"def edaN : Nat := {n_edges}",
        f"def edaM : Nat := {m_sites}",
        f"def edaLengths : Array (Array Int) := {_lean_array_2d(lengths_matrix)}",
        f"def edaAllowed : Array (Array Bool) := {_lean_array_2d(allowed_matrix)}",
    ]

    if has_hall:
        blocking_ids = list(raw_cert["hall_blocking_set"])
        blocking_indices = [edge_index[eid] for eid in blocking_ids]
        allowed_below = _allowed_matrix(t_bound - 1)
        nbhd_indices = sorted({
            s_idx
            for e_idx in blocking_indices
            for s_idx, flag in enumerate(allowed_below[e_idx])
            if flag == "true"
        })
        lines.extend([
            f"def edaAllowedBelow : Array (Array Bool) := {_lean_array_2d(allowed_below)}",
            f"def edaHallBlocking : List Nat := {_lean_list([str(i) for i in blocking_indices])}",
            f"def edaHallNeighborhood : List Nat := {_lean_list([str(i) for i in nbhd_indices])}",
            "",
            "theorem eda_hall_conflict :",
            "    ¬ ∃ assign', IsFeasibleMatching edaN edaM (getCellBool edaAllowedBelow) assign' :=",
            "  verify_eda_hall_conflict_sound edaN edaM edaAllowedBelow edaHallBlocking edaHallNeighborhood",
            "    (by decide) (by decide) (by rfl)",
            "",
        ])

    if has_dual:
        if cert_status == "verified":
            u_vals = [str(int(raw_cert["row_potentials"][edge.id])) for edge in movable]
            v_vals = [str(int(raw_cert["site_potentials"][site_id])) for site_id in sites]
        else:
            u_vals = [str(geometric_length(instance, edge, assignment[edge.id])) for edge in movable]
            v_vals = ["0" for _ in sites]
        lines.extend([
            f"def edaU : Array Int := {_lean_array_1d(u_vals)}",
            f"def edaV : Array Int := {_lean_array_1d(v_vals)}",
            f"def edaAssign : Array Nat := {_lean_array_1d(assign_indices)}",
            "",
            f"theorem {theorem_name} :",
            "    IsFeasibleMatching edaN edaM (getCellBool edaAllowed) (getNat edaAssign) ∧",
            "    (∀ assign', IsFeasibleMatching edaN edaM (getCellBool edaAllowed) assign' →",
            "      sumInt edaN (fun e => getCellInt edaLengths e (getNat edaAssign e)) ≤",
            "      sumInt edaN (fun e => getCellInt edaLengths e (assign' e))) :=",
            "  verify_eda_optimal_sound edaN edaM edaLengths edaAllowed edaU edaV edaAssign",
            "    (by rfl) (by rfl) (by rfl) (by rfl) (by rfl)",
            "",
            f"#print axioms {theorem_name}",
        ])
        if has_hall:
            lines.append("#print axioms eda_hall_conflict")
        cert_kind = "eda_hall_and_dual_optimal_lean" if has_hall else "eda_finite_optimal_lean"
    else:
        cert_kind = "eda_hall_lower_bound_lean"
        theorem_name = "eda_hall_conflict"
        lines.append(f"#print axioms {theorem_name}")

    lines.append("")
    return {
        "instance_id": instance.instance_id,
        "theorem_name": theorem_name,
        "certificate_kind": cert_kind,
        "movable_edges": n_edges,
        "candidate_sites": m_sites,
        "t_lower_bound": t_bound,
        "objectives": list(eval_result.objectives),
        "lower_bound": list(eval_result.lower_bound),
        "lean_source": "\n".join(lines),
    }
