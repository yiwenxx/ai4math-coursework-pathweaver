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


def export_jsp158_cyclic_lean_certificate(
    m: int,
    palette_limit: int,
    colors: list[int],
    *,
    theorem_name: str | None = None,
) -> dict[str, Any]:
    """Recompute exhaustive cyclic ABBA validity and emit a kernel-checked Lean 4 proof."""
    if type(m) is not int or m < 2:
        raise ValueError("m must be an integer >= 2")
    if type(palette_limit) is not int or palette_limit < 1:
        raise ValueError("palette_limit must be an integer >= 1")
    if not isinstance(colors, list) or len(colors) != m:
        raise ValueError(f"Expected exactly {m} color labels")
    if any(type(c) is not int or not 0 <= c < palette_limit for c in colors):
        raise ValueError(f"Color labels must be integers in [0,{palette_limit - 1}]")

    violations = 0
    for a in range(m):
        for d in range(1, m):
            if colors[a] == colors[(a + 3 * d) % m] and colors[(a + d) % m] == colors[(a + 2 * d) % m]:
                violations += 1
    if violations > 0:
        raise ValueError(f"Cannot export Lean certificate for invalid cyclic ABBA template ({violations} violations)")

    used_colors = len(set(colors))
    thm = theorem_name or f"jsp158_cyclic_m{m}_r{palette_limit}_valid"
    colors_arr = "#[" + ", ".join(str(int(c)) for c in colors) + "]"
    lean_source = "\n".join([
        "import PathWeaverFormal.Jsp158Coloring",
        "",
        f"-- Cyclic ABBA-free template: m = {m}, palette_limit = {palette_limit}, distinct colors = {used_colors}",
        "open PathWeaverFormal.Jsp158",
        "",
        f"def jspCyclicColors : Array Nat := {colors_arr}",
        "",
        f"theorem {thm} :",
        f"    IsCyclicABBAFree jspCyclicColors ∧",
        f"    AllColorsBelow jspCyclicColors {palette_limit} ∧",
        f"    jspCyclicColors.size = {m} :=",
        f"  ⟨checkCyclicABBAFree_sound jspCyclicColors (by rfl),",
        f"   checkColorsBelow_sound jspCyclicColors {palette_limit} (by rfl),",
        f"   by rfl⟩",
        "",
        f"#print axioms {thm}",
        "",
    ])
    return {
        "m": m,
        "palette_limit": palette_limit,
        "used_colors": used_colors,
        "crosses_quarter_threshold": m > used_colors ** 4,
        "theorem_name": thm,
        "certificate_kind": "jsp158_cyclic_abba_lean",
        "lean_source": lean_source,
    }
