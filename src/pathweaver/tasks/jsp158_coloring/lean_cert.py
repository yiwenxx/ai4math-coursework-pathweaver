"""Export independent JSP-000158 finite 4-AP coloring certificates to Lean 4."""
from collections.abc import Mapping
from typing import Any

from .evaluator import evaluate_prepared, prepare_verifier


def export_jsp158_lean_certificate(
    raw_instance: Mapping[str, Any],
    solution: Mapping[str, Any],
    *,
    theorem_name: str = "jsp158_four_ap_valid",
) -> dict[str, Any]:
    """Recompute exhaustive 4-AP validity and emit a kernel-checked Lean 4 proof."""
    prepared = prepare_verifier(raw_instance)
    instance = prepared.instance
    eval_result = evaluate_prepared(prepared, solution)
    if not eval_result.feasible or eval_result.objectives is None:
        raise ValueError(
            "Cannot export Lean certificate for invalid JSP-000158 coloring: "
            + "; ".join(eval_result.violations[:4])
        )

    colors = [int(c) for c in solution["solution"]["colors"]]
    colors_arr = "#[" + ", ".join(str(c) for c in colors) + "]"
    lean_source = "\n".join([
        "import PathWeaverFormal.Jsp158Coloring",
        "",
        f"-- Instance: {instance.instance_id} (N = {instance.n}, distinct colors = {eval_result.objectives[0]})",
        "open PathWeaverFormal.Jsp158",
        "",
        f"def jspColors : Array Nat := {colors_arr}",
        "",
        f"theorem {theorem_name} : IsFourAPFree3 jspColors ∧ jspColors.size = {instance.n} :=",
        "  ⟨checkFourAPFree3_sound jspColors (by rfl), by rfl⟩",
        "",
        f"#print axioms {theorem_name}",
        "",
    ])
    return {
        "instance_id": instance.instance_id,
        "theorem_name": theorem_name,
        "certificate_kind": "jsp158_finite_coloring_lean",
        "n": instance.n,
        "color_count": eval_result.objectives[0],
        "lean_source": lean_source,
    }
