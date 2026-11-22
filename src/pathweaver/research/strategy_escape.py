"""Domain-neutral AST regime classifier and orthogonal paradigm-refactoring engine.

Detects when evolutionary search is trapped in first-order local tweaks (e.g.,
weight/penalty adjustments inside a greedy or matching template) and triggers a
targeted global paradigm jump using task-declared mathematical reformulations.
"""
import ast
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


DEFAULT_PARADIGM_CATALOG: tuple[dict[str, str], ...] = (
    {
        "id": "exact_branch_and_reduce",
        "regime": "exact_branch_and_reduce",
        "title": "Bounded Branch-and-Bound / Beam Search with Structural Reduction",
        "mechanism": "Replace single-trajectory greedy tweaks with dominance pruning, unit/forced propagation, and bounded-width beam or branch-and-bound exploration.",
        "anti_pattern": "Do not adjust greedy scoring tie-breakers or iterative reweighting coefficients.",
    },
    {
        "id": "algebraic_modular_group",
        "regime": "algebraic_modular_group",
        "title": "Algebraic / Modular / Quotient-Group Construction",
        "mechanism": "Replace iterative search with closed-form modular, polynomial, residue-class, or group-orbit structural constructions.",
        "anti_pattern": "Do not perform hill-climbing or single-element local descent from a trivial seed.",
    },
    {
        "id": "spectral_relaxation_rounding",
        "regime": "spectral_relaxation_rounding",
        "title": "Lagrangian Dual / Spectral Relaxation & Randomized Rounding",
        "mechanism": "Relax hard coupling constraints via subgradient Lagrangian multipliers or spectral/Laplacian scores, then repair/round into feasibility.",
        "anti_pattern": "Do not rely on myopic bottleneck edge/vertex weight bumps alone.",
    },
    {
        "id": "metaheuristic_population",
        "regime": "metaheuristic_population",
        "title": "Large-Neighborhood Destroy-and-Repair / Simulated Annealing",
        "mechanism": "Escape 1-opt/2-opt basins by destroying coupled structural blocks (20-40% of variables) and reconstructing via exact subproblem solvers.",
        "anti_pattern": "Do not restrict moves to single-variable greedy flips.",
    },
)


def classify_algorithmic_regime(source: str, *, language: str = "auto") -> str:
    """Classify Python or Lean candidate source into a coarse paradigm family."""
    if not isinstance(source, str) or not source.strip():
        return "general_constructive"
    if language == "lean" or (language == "auto" and (":=" in source and ("theorem " in source or "by" in source))):
        lowered = source.lower()
        if any(tok in lowered for tok in ("induction ", "cases ", "rcases ", "match ")):
            return "induction_case_analysis"
        if any(tok in lowered for tok in ("calc", "rw [", "simp", "ring", "linarith", "omega")):
            return "algebraic_rewriting_automation"
        if any(tok in lowered for tok in ("have ", "lemma ", "obtain ", "refine ")):
            return "structured_lemma_decomposition"
        return "tactic_automation"
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return "general_constructive"

    names: set[str] = set()
    has_recursion = False
    mod_ops = 0
    exp_calls = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == node.name:
                    has_recursion = True
        elif isinstance(node, ast.Name):
            names.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
            if node.attr == "exp":
                exp_calls += 1
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            mod_ops += 1

    joined = " ".join(sorted(names))
    if any(tok in joined for tok in ("hungarian", "augment", "bipartite", "matching", "min_cost", "flow")):
        return "bipartite_matching_flow"
    if any(tok in joined for tok in ("lagrang", "subgradient", "spectral", "laplacian", "eigen", "simplex", "dual_bound")):
        return "spectral_relaxation_rounding"
    if has_recursion or any(tok in joined for tok in ("branch", "backtrack", "bnb", "lru_cache", "memo", "beam")):
        return "exact_branch_and_reduce"
    if mod_ops >= 3 or any(tok in joined for tok in ("frobenius", "finite_field", "galois", "coset", "orbit", "quotient", "cubic")):
        return "algebraic_modular_group"
    if exp_calls > 0 or any(tok in joined for tok in ("anneal", "temperature", "tabu", "destroy", "lns", "ruin")):
        return "metaheuristic_population"
    if any(tok in joined for tok in ("greedy", "swap", "recolor", "local", "weight", "pressure", "prune", "descent")):
        return "greedy_local_search"
    return "general_constructive"


@dataclass(frozen=True)
class ParadigmDirective:
    trapped_regime: str
    stagnation_streak: int
    recommended_id: str
    recommended_regime: str
    title: str
    mechanism: str
    anti_pattern: str
    persistent_gap: int | None = None
    failure_pattern: str = ""

    def format_prompt_block(self) -> str:
        lines = [
            "## PATHWEAVER PARADIGM REFACTORING DIRECTIVE (ESCAPING LOCAL OPTIMUM)",
            f"- Trapped Regime: `{self.trapped_regime}` ({self.stagnation_streak} consecutive evaluations without exact-tuple progress).",
        ]
        if self.persistent_gap is not None and self.persistent_gap > 0:
            lines.append(f"- Persistent Certified Bound Gap: {self.persistent_gap} (first-order tweaks have not closed this gap).")
        if self.failure_pattern:
            lines.append(f"- Recurring Structural Bottleneck: {self.failure_pattern}")
        lines.extend([
            f"- Target Orthogonal Paradigm: **{self.title}** (`{self.recommended_regime}`)",
            f"- Required Algorithmic Refactoring: {self.mechanism}",
            f"- Anti-Pattern Warning: {self.anti_pattern}",
            "- Instruction: Do NOT submit minor weight/threshold tweaks on the parent; implement the target structural paradigm while keeping valid fallback guarantees.",
        ])
        return "\n".join(lines)


class StructuralStagnationMonitor:
    """Monitors exact-tuple progress and AST regime diversity across discovery attempts."""

    def __init__(self, *, stagnation_window: int = 4, cooldown_steps: int = 2):
        self.stagnation_window = max(2, int(stagnation_window))
        self.cooldown_steps = max(1, int(cooldown_steps))
        self.best_objectives: tuple[int, ...] | None = None
        self.no_improve_streak: int = 0
        self.history: list[dict[str, Any]] = []
        self.paradigm_attempts: Counter[str] = Counter()
        self.steps_since_trigger: int = self.cooldown_steps
        self.last_directive: ParadigmDirective | None = None

    def record(
        self,
        candidate_id: str,
        source: str,
        objectives: Sequence[int] | None,
        *,
        bound_gap: int | None = None,
        failure_summary: str = "",
    ) -> None:
        regime = classify_algorithmic_regime(source)
        improved = False
        if objectives is not None:
            obj_tuple = tuple(int(v) for v in objectives)
            if self.best_objectives is None or obj_tuple < self.best_objectives:
                self.best_objectives = obj_tuple
                self.no_improve_streak = 0
                improved = True
            else:
                self.no_improve_streak += 1
        else:
            self.no_improve_streak += 1

        self.steps_since_trigger += 1
        self.history.append({
            "candidate_id": candidate_id,
            "regime": regime,
            "objectives": list(objectives) if objectives is not None else None,
            "bound_gap": bound_gap,
            "failure_summary": failure_summary[:240],
            "improved": improved,
        })
        if len(self.history) > 64:
            self.history.pop(0)

    def detect_local_trap(
        self,
        catalog: Sequence[dict[str, str]] | None = None,
        *,
        obstructed_regimes: Sequence[str] = (),
    ) -> ParadigmDirective | None:
        if self.no_improve_streak < self.stagnation_window:
            return None
        if self.steps_since_trigger < self.cooldown_steps and self.last_directive is not None:
            return self.last_directive

        recent = self.history[-self.stagnation_window:]
        regime_counts = Counter(row["regime"] for row in recent)
        trapped_regime = regime_counts.most_common(1)[0][0] if regime_counts else "greedy_local_search"
        dominant_ratio = regime_counts[trapped_regime] / max(1, len(recent))

        gaps = [row["bound_gap"] for row in recent if isinstance(row.get("bound_gap"), int)]
        min_gap = min(gaps) if gaps else None

        # Trigger if dominant regime collapsed (>= 50% of stagnating window) OR streak is long (>= window + 2).
        if dominant_ratio < 0.5 and self.no_improve_streak < self.stagnation_window + 2:
            return None

        palette = list(catalog) if catalog else list(DEFAULT_PARADIGM_CATALOG)
        blocked = set(obstructed_regimes) | {trapped_regime}
        candidates = [entry for entry in palette if entry.get("regime") not in blocked]
        if not candidates:
            candidates = [entry for entry in palette if entry.get("regime") != trapped_regime] or palette

        # Select least-tried orthogonal paradigm deterministically.
        chosen = min(candidates, key=lambda entry: (self.paradigm_attempts[entry["id"]], entry["id"]))
        self.paradigm_attempts[chosen["id"]] += 1
        self.steps_since_trigger = 0

        failure_pattern = next(
            (row["failure_summary"] for row in reversed(recent) if row.get("failure_summary")),
            "",
        )
        directive = ParadigmDirective(
            trapped_regime=trapped_regime,
            stagnation_streak=self.no_improve_streak,
            recommended_id=chosen["id"],
            recommended_regime=chosen["regime"],
            title=chosen["title"],
            mechanism=chosen["mechanism"],
            anti_pattern=chosen["anti_pattern"],
            persistent_gap=min_gap,
            failure_pattern=failure_pattern,
        )
        self.last_directive = directive
        return directive
