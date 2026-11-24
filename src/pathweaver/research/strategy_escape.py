"""Domain-neutral AST regime classifier and orthogonal paradigm-refactoring engine.

Detects when evolutionary search is trapped in first-order local tweaks (e.g.,
weight/penalty adjustments inside a greedy or matching template) and triggers a
targeted global paradigm jump using task-declared mathematical reformulations.
"""
import ast
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import re
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


_EXTERNAL_SOLVER_ROOTS = frozenset({
    "scipy", "ortools", "pulp", "cvxpy", "z3", "pysat", "networkx",
    "igraph", "highs", "highspy", "gurobipy", "mip", "sympy", "cvxopt",
})
_HEAP_DEQUE_NAMES = frozenset({
    "heapq", "heappush", "heappop", "heapify", "heappushpop", "heapreplace",
    "nsmallest", "nlargest", "deque", "popleft", "appendleft", "priorityqueue", "lifoqueue",
})
_TRAVERSAL_TOKENS = frozenset({
    "visited", "vis", "seen", "parent", "prev", "pred", "way", "dist",
    "level", "match", "pair", "flow", "residual", "cap", "capacity",
    "augment", "queue", "stack", "used", "path",
})
_DUAL_TOKENS = frozenset({
    "dual", "lagrang", "lagrangian", "subgradient", "potential", "multiplier",
    "multipliers", "spectral", "laplacian", "eigen", "simplex", "reduced",
    "primal", "slack", "relax", "relaxation", "lam", "lambdas", "pi",
    "lr", "step_size",
})
_SPECTRAL_LP_NAMES = frozenset({
    "eig", "eigh", "eigvals", "eigvalsh", "eigsh", "svd", "linprog", "milp",
    "cvxpy", "pulp", "highs", "highspy", "gurobipy", "cvxopt",
})
_MATCHING_SOLVER_NAMES = frozenset({
    "linear_sum_assignment", "minimum_weight_full_matching",
    "maximum_bipartite_matching", "maximum_flow", "min_cost_flow",
    "max_weight_matching", "bipartite",
})
_EXACT_SOLVER_NAMES = frozenset({"z3", "pysat", "cp_model"})

_EMPTY_FINGERPRINT: dict[str, Any] = {
    "max_loop_depth": 0,
    "has_recursion": False,
    "has_heap_or_deque": False,
    "has_augmenting_bfs_dfs": False,
    "has_dual_potential_update": False,
    "has_backtrack_pruning": False,
    "mod_arith_density": 0.0,
    "has_exp_or_anneal": False,
    "uses_external_solver": False,
    "function_count": 0,
}


def _strip_lean_comments(source: str) -> str:
    no_block = re.sub(r"/-.*?-/", " ", source, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", "", no_block)


def _is_lean_source(source: str, language: str) -> bool:
    if language == "lean":
        return True
    if language != "auto":
        return False
    if ":=" not in source:
        return False
    if not re.search(r"\b(?:theorem|lemma|example|by)\b", source):
        return False
    try:
        ast.parse(source)
        return False
    except SyntaxError:
        return True


def _split_tokens(names: set[str]) -> set[str]:
    tokens: set[str] = set()
    for name in names:
        low = name.lower()
        tokens.add(low)
        for part in re.split(r"[^a-z0-9]+", low):
            if part:
                tokens.add(part)
    return tokens


def _distinct_keyword_hits(names: set[str], tokens: set[str], keywords: Sequence[str], *, exact_tokens: frozenset[str] = frozenset()) -> int:
    hits = 0
    for kw in keywords:
        if kw in exact_tokens:
            if kw in tokens:
                hits += 1
        elif any(kw in name for name in names):
            hits += 1
    return hits


def _analyze_python_source(source: str) -> tuple[dict[str, Any], set[str], set[str], set[str], int, bool]:
    """Return (fingerprint, raw_lower_names, split_tokens, imported_names, mod_ops, has_sort_call)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return dict(_EMPTY_FINGERPRINT), set(), set(), set(), 0, False

    names: set[str] = set()
    imported: set[str] = set()
    func_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    max_loop_depth = 0
    mod_ops = 0
    total_ops = 0
    has_exp_call = False
    has_sort_call = False
    uses_external_solver = False
    has_heap_or_deque = False
    has_while_loop = False
    has_pop_in_loop = False
    has_subscript_write_in_loop = False
    has_subscript_arith_in_loop = False
    has_projected_max_zero = False
    has_anneal_loop = False
    has_beam_or_stack_prune = False
    has_random_call = False

    def _is_zero_const(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and node.value == 0

    def _visit(node: ast.AST, loop_depth: int, in_fn: str | None) -> None:
        nonlocal max_loop_depth, mod_ops, total_ops, has_exp_call, has_sort_call
        nonlocal uses_external_solver, has_heap_or_deque, has_while_loop
        nonlocal has_pop_in_loop, has_subscript_write_in_loop, has_subscript_arith_in_loop
        nonlocal has_projected_max_zero, has_anneal_loop, has_beam_or_stack_prune, has_random_call

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_nodes.append(node)
            names.add(node.name.lower())
            for child in ast.iter_child_nodes(node):
                _visit(child, 0, node.name)
            return

        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.lower()
                imported.add(mod)
                root = mod.split(".", 1)[0]
                imported.add(root)
                if root in _EXTERNAL_SOLVER_ROOTS or mod.startswith(("numpy.linalg", "scipy.")):
                    uses_external_solver = True
                if root in _HEAP_DEQUE_NAMES or mod == "collections":
                    if root == "heapq":
                        has_heap_or_deque = True
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").lower()
            if mod:
                imported.add(mod)
                root = mod.split(".", 1)[0]
                imported.add(root)
                if root in _EXTERNAL_SOLVER_ROOTS or mod.startswith(("numpy.linalg", "scipy.")):
                    uses_external_solver = True
                if root == "heapq":
                    has_heap_or_deque = True
            for alias in node.names:
                aname = alias.name.lower()
                imported.add(aname)
                if aname in _HEAP_DEQUE_NAMES:
                    has_heap_or_deque = True
                if aname in _EXTERNAL_SOLVER_ROOTS:
                    uses_external_solver = True

        elif isinstance(node, ast.Name):
            low = node.id.lower()
            names.add(low)
            if low in _HEAP_DEQUE_NAMES:
                has_heap_or_deque = True
        elif isinstance(node, ast.Attribute):
            low = node.attr.lower()
            names.add(low)
            if low in _HEAP_DEQUE_NAMES:
                has_heap_or_deque = True
            if low == "exp":
                has_exp_call = True
            if low in {"random", "uniform", "randint", "choice", "randrange"}:
                has_random_call = True
        elif isinstance(node, ast.BinOp):
            total_ops += 1
            if isinstance(node.op, ast.Mod):
                mod_ops += 1
        elif isinstance(node, ast.AugAssign):
            total_ops += 1
            if isinstance(node.op, ast.Mod):
                mod_ops += 1
            if loop_depth > 0 and isinstance(node.target, ast.Subscript):
                has_subscript_write_in_loop = True
                if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                    has_subscript_arith_in_loop = True
            if loop_depth > 0 and isinstance(node.op, ast.Mult) and isinstance(node.target, ast.Name):
                tname = node.target.id.lower()
                if any(tok in tname for tok in ("temp", "anneal", "cool", "lr", "alpha", "step")):
                    has_anneal_loop = True
        elif isinstance(node, ast.Assign):
            if loop_depth > 0:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Subscript):
                        has_subscript_write_in_loop = True
                        if any(isinstance(sub, ast.BinOp) for sub in ast.walk(node.value)):
                            has_subscript_arith_in_loop = True
        elif isinstance(node, ast.Call):
            total_ops += 1
            func = node.func
            cname = func.id.lower() if isinstance(func, ast.Name) else (func.attr.lower() if isinstance(func, ast.Attribute) else "")
            if cname == "exp":
                has_exp_call = True
            elif cname in {"sorted", "sort"}:
                has_sort_call = True
            elif cname == "divmod" or (cname == "pow" and len(node.args) == 3):
                mod_ops += 1
            elif cname in _HEAP_DEQUE_NAMES:
                has_heap_or_deque = True
            elif cname in {"random", "uniform", "randint", "randrange"}:
                has_random_call = True
            elif cname == "max" and len(node.args) == 2 and (_is_zero_const(node.args[0]) or _is_zero_const(node.args[1])):
                has_projected_max_zero = True
            if loop_depth > 0 and cname in {"pop", "popleft"}:
                has_pop_in_loop = True

        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            if isinstance(node, ast.While):
                has_while_loop = True
            next_depth = loop_depth + 1
            if next_depth > max_loop_depth:
                max_loop_depth = next_depth
            if isinstance(node, ast.While):
                has_pop = False
                has_prune_if = False
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in {"pop", "popleft"}:
                        has_pop = True
                    elif isinstance(sub, ast.If) and any(isinstance(b, (ast.Continue, ast.Break, ast.Return)) for b in ast.walk(sub)):
                        has_prune_if = True
                if has_pop and has_prune_if:
                    has_beam_or_stack_prune = True
            for child in ast.iter_child_nodes(node):
                _visit(child, next_depth, in_fn)
            return

        for child in ast.iter_child_nodes(node):
            _visit(child, loop_depth, in_fn)

    _visit(tree, 0, None)

    # Check direct and 2-cycle mutual recursion plus recursive structural patterns.
    func_names = {fn.name for fn in func_nodes}
    call_graph: dict[str, set[str]] = {fn.name: set() for fn in func_nodes}
    fn_has_loop: dict[str, bool] = {}
    fn_has_prune_or_memo: dict[str, bool] = {}
    fn_has_subscript_write: dict[str, bool] = {}
    for fn in func_nodes:
        has_loop = False
        has_prune = False
        has_sub_write = False
        for dec in fn.decorator_list:
            dname = dec.id.lower() if isinstance(dec, ast.Name) else (dec.attr.lower() if isinstance(dec, ast.Attribute) else "")
            if "cache" in dname or "memo" in dname:
                has_prune = True
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in func_names:
                call_graph[fn.name].add(sub.func.id)
            elif isinstance(sub, (ast.For, ast.AsyncFor, ast.While)):
                has_loop = True
            elif isinstance(sub, ast.If) and any(isinstance(b, (ast.Return, ast.Continue, ast.Break)) for b in ast.walk(sub)):
                has_prune = True
            elif isinstance(sub, (ast.Assign, ast.AugAssign)):
                targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                if any(isinstance(t, ast.Subscript) for t in targets):
                    has_sub_write = True
        fn_has_loop[fn.name] = has_loop
        fn_has_prune_or_memo[fn.name] = has_prune
        fn_has_subscript_write[fn.name] = has_sub_write

    recursive_fns: set[str] = set()
    for fname, callees in call_graph.items():
        if fname in callees or any(fname in call_graph.get(other, ()) for other in callees if other != fname):
            recursive_fns.add(fname)

    has_recursion = bool(recursive_fns)
    tokens = _split_tokens(names | imported)
    has_traversal_token = bool(tokens & _TRAVERSAL_TOKENS)
    has_dual_token = bool(tokens & _DUAL_TOKENS)

    has_augmenting_bfs_dfs = bool(
        (has_subscript_write_in_loop or any(fn_has_subscript_write.get(f, False) for f in recursive_fns))
        and (
            (has_heap_or_deque and max_loop_depth >= 2)
            or (any(fn_has_loop.get(f, False) for f in recursive_fns) and has_traversal_token)
            or (has_while_loop and max_loop_depth >= 2 and (has_pop_in_loop or has_traversal_token))
        )
    )
    has_dual_potential_update = bool(
        bool((tokens | imported) & _SPECTRAL_LP_NAMES)
        or (has_subscript_arith_in_loop and (has_dual_token or has_projected_max_zero))
    )
    has_backtrack_pruning = bool(
        any(fn_has_prune_or_memo.get(f, False) for f in recursive_fns)
        or (has_beam_or_stack_prune and bool(tokens & {"beam", "branch", "bnb", "bound", "backtrack", "prune", "best"}))
    )
    has_exp_or_anneal = bool(
        has_exp_call
        or (has_anneal_loop and has_random_call)
        or (max_loop_depth >= 1 and has_random_call and bool(tokens & {"anneal", "tabu", "metropolis", "ruin", "destroy"}))
    )
    mod_arith_density = round(min(1.0, mod_ops / max(1, total_ops)), 4)

    fp = {
        "max_loop_depth": max_loop_depth,
        "has_recursion": has_recursion,
        "has_heap_or_deque": has_heap_or_deque,
        "has_augmenting_bfs_dfs": has_augmenting_bfs_dfs,
        "has_dual_potential_update": has_dual_potential_update,
        "has_backtrack_pruning": has_backtrack_pruning,
        "mod_arith_density": mod_arith_density,
        "has_exp_or_anneal": has_exp_or_anneal,
        "uses_external_solver": uses_external_solver,
        "function_count": len(func_nodes),
    }
    return fp, names, tokens, imported, mod_ops, has_sort_call


def extract_ast_fingerprint(source: str, *, language: str = "auto") -> dict[str, Any]:
    """Extract structural algorithmic signals from Python AST or Lean tactic blocks."""
    if not isinstance(source, str) or not source.strip():
        return dict(_EMPTY_FINGERPRINT)
    if _is_lean_source(source, language):
        cleaned = _strip_lean_comments(source)
        lowered = cleaned.lower()
        decls = re.findall(
            r"^\s*(?:private\s+|noncomputable\s+|protected\s+)?(?:theorem|lemma|def|instance|example)\s+([A-Za-z0-9_']+)",
            cleaned,
            flags=re.MULTILINE,
        )
        tactic_branch_hits = len(re.findall(r"\b(?:induction|cases|rcases|match|repeat|iterate)\b", lowered))
        has_recursion = "termination_by" in lowered or "decreasing_by" in lowered or any(
            len(re.findall(rf"\b{re.escape(name)}\b", cleaned)) >= 2 for name in decls
        )
        has_backtrack = any(tok in lowered for tok in ("by_cases", "contradiction", "exfalso", "aesop", "decide", "omega"))
        return {
            "max_loop_depth": min(4, tactic_branch_hits),
            "has_recursion": has_recursion,
            "has_heap_or_deque": False,
            "has_augmenting_bfs_dfs": False,
            "has_dual_potential_update": False,
            "has_backtrack_pruning": has_backtrack,
            "mod_arith_density": round(min(1.0, len(re.findall(r"\bmod\b|%", lowered)) / max(1, len(cleaned.splitlines()))), 4),
            "has_exp_or_anneal": False,
            "uses_external_solver": any(tok in lowered for tok in ("smt", "duper", "egg")),
            "function_count": len(decls),
        }
    fp, _, _, _, _, _ = _analyze_python_source(source)
    return fp


def classify_algorithmic_regime(source: str, *, language: str = "auto") -> str:
    """Classify Python or Lean candidate source into a coarse paradigm family."""
    if not isinstance(source, str) or not source.strip():
        return "general_constructive"
    if _is_lean_source(source, language):
        lowered = _strip_lean_comments(source).lower()
        if any(tok in lowered for tok in ("induction ", "cases ", "rcases ", "match ")):
            return "induction_case_analysis"
        if any(tok in lowered for tok in ("calc", "rw [", "simp", "ring", "linarith", "omega")):
            return "algebraic_rewriting_automation"
        if any(tok in lowered for tok in ("have ", "lemma ", "obtain ", "refine ")):
            return "structured_lemma_decomposition"
        return "tactic_automation"

    fp, names, tokens, imported, mod_ops, has_sort_call = _analyze_python_source(source)
    if not names and not imported and fp["function_count"] == 0:
        return "general_constructive"

    matching_kws = _distinct_keyword_hits(
        names, tokens,
        ("hungarian", "augment", "bipartite", "matching", "min_cost", "max_flow", "hopcroft", "dinic", "edmonds", "flow", "match"),
        exact_tokens=frozenset({"flow", "match"}),
    )
    uses_matching_solver = bool((tokens | imported) & _MATCHING_SOLVER_NAMES)
    if (
        uses_matching_solver
        or (fp["has_augmenting_bfs_dfs"] and matching_kws >= 1)
        or (matching_kws >= 2 and (fp["max_loop_depth"] >= 2 or fp["has_heap_or_deque"] or fp["has_recursion"]))
        or matching_kws >= 3
    ):
        return "bipartite_matching_flow"

    spectral_kws = _distinct_keyword_hits(
        names, tokens,
        ("lagrang", "subgradient", "spectral", "laplacian", "eigen", "simplex", "dual_bound", "eigval", "svd", "linprog", "milp", "relaxation", "multiplier"),
    )
    uses_spectral_lp_solver = bool((tokens | imported) & _SPECTRAL_LP_NAMES)
    if (
        uses_spectral_lp_solver
        or (fp["has_dual_potential_update"] and spectral_kws >= 1)
        or (spectral_kws >= 2 and (fp["max_loop_depth"] >= 1 or fp["uses_external_solver"]))
    ):
        return "spectral_relaxation_rounding"

    branch_kws = _distinct_keyword_hits(
        names, tokens,
        ("branch", "backtrack", "bnb", "lru_cache", "memo", "beam", "prune", "lower_bound", "upper_bound", "kerneliz", "dsatur", "dominance"),
        exact_tokens=frozenset({"bnb"}),
    )
    uses_exact_solver = bool((tokens | imported) & _EXACT_SOLVER_NAMES)
    if (
        uses_exact_solver
        or fp["has_backtrack_pruning"]
        or (fp["has_recursion"] and (branch_kws >= 1 or fp["max_loop_depth"] >= 1))
        or (branch_kws >= 2 and (fp["max_loop_depth"] >= 2 or fp["has_heap_or_deque"] or fp["has_recursion"]))
    ):
        return "exact_branch_and_reduce"

    algebraic_kws = _distinct_keyword_hits(
        names, tokens,
        ("frobenius", "finite_field", "galois", "coset", "orbit", "quotient", "cubic", "residue", "cyclotomic", "gf", "modular", "poly", "polynomial"),
        exact_tokens=frozenset({"gf", "poly"}),
    )
    uses_algebraic_solver = "sympy" in imported or "galois" in imported
    if (
        uses_algebraic_solver
        or (mod_ops >= 3 and fp["mod_arith_density"] >= 0.08 and (fp["max_loop_depth"] >= 1 or algebraic_kws >= 1))
        or (mod_ops >= 2 and fp["mod_arith_density"] >= 0.12 and fp["max_loop_depth"] >= 1)
        or (mod_ops >= 2 and algebraic_kws >= 1 and fp["mod_arith_density"] >= 0.04)
        or (algebraic_kws >= 2 and (mod_ops >= 1 or fp["function_count"] >= 1))
    ):
        return "algebraic_modular_group"

    meta_kws = _distinct_keyword_hits(
        names, tokens,
        ("anneal", "temperature", "tabu", "destroy", "lns", "ruin", "reheat", "metropolis", "crossover", "mutation", "population"),
        exact_tokens=frozenset({"lns"}),
    )
    if (fp["has_exp_or_anneal"] and (fp["max_loop_depth"] >= 1 or meta_kws >= 1)) or (meta_kws >= 2 and fp["max_loop_depth"] >= 1):
        return "metaheuristic_population"

    greedy_kws = _distinct_keyword_hits(
        names, tokens,
        ("greedy", "swap", "recolor", "local", "weight", "pressure", "prune", "descent", "degree", "ratio", "score", "heuristic"),
    )
    if (greedy_kws >= 1 and (fp["max_loop_depth"] >= 1 or has_sort_call)) or greedy_kws >= 2:
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
            "- Structural Refactor Permission: You may replace the entire `def solve` function body (matching `def solve` and adding required imports/helpers) in a single clean `<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE` block rather than piecemeal line diffs.",
        ])
        return "\n".join(lines)


class StructuralStagnationMonitor:
    """Monitors exact-tuple progress and AST regime diversity across discovery attempts."""

    def __init__(self, *, stagnation_window: int = 4, cooldown_steps: int = 2, language: str = "auto"):
        self.stagnation_window = max(2, int(stagnation_window))
        self.cooldown_steps = max(1, int(cooldown_steps))
        self.language = language
        self.best_objectives: tuple[int, ...] | None = None
        self.no_improve_streak: int = 0
        self.history: list[dict[str, Any]] = []
        self.paradigm_attempts: Counter[str] = Counter()
        self.regime_attempts: Counter[str] = Counter()
        self.regime_improvements: Counter[str] = Counter()
        self.regime_trap_triggers: Counter[str] = Counter()
        self.empirical_obstructed_regimes: dict[str, str] = {}
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
        regime = classify_algorithmic_regime(source, language=self.language)
        self.regime_attempts[regime] += 1
        improved = False
        if objectives is not None:
            obj_tuple = tuple(int(v) for v in objectives)
            if self.best_objectives is None or obj_tuple < self.best_objectives:
                self.best_objectives = obj_tuple
                self.no_improve_streak = 0
                improved = True
                self.regime_improvements[regime] += 1
                self.empirical_obstructed_regimes.pop(regime, None)
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

        self.regime_trap_triggers[trapped_regime] += 1
        stalled_in_regime = (
            sum(
                1 for row in self.history[-5:]
                if row.get("regime") == trapped_regime and not row.get("improved")
            ) >= 5
        )
        if self.regime_trap_triggers[trapped_regime] >= 2 and stalled_in_regime:
            self.empirical_obstructed_regimes[trapped_regime] = (
                "repeated empirical stagnation without exact-tuple progress"
            )

        palette = list(catalog) if catalog else list(DEFAULT_PARADIGM_CATALOG)
        blocked = set(obstructed_regimes) | set(self.empirical_obstructed_regimes) | {trapped_regime}
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "stagnation_window": self.stagnation_window,
            "cooldown_steps": self.cooldown_steps,
            "language": self.language,
            "best_objectives": list(self.best_objectives) if self.best_objectives is not None else None,
            "no_improve_streak": self.no_improve_streak,
            "history": list(self.history),
            "paradigm_attempts": dict(self.paradigm_attempts),
            "regime_attempts": dict(self.regime_attempts),
            "regime_improvements": dict(self.regime_improvements),
            "regime_trap_triggers": dict(self.regime_trap_triggers),
            "empirical_obstructed_regimes": dict(self.empirical_obstructed_regimes),
            "steps_since_trigger": self.steps_since_trigger,
            "last_directive": asdict(self.last_directive) if self.last_directive is not None else None,
        }

    def load_state(self, raw: Mapping[str, Any]) -> None:
        if not isinstance(raw, Mapping):
            return
        best = raw.get("best_objectives")
        self.best_objectives = tuple(int(v) for v in best) if isinstance(best, list) and best else None
        self.no_improve_streak = int(raw.get("no_improve_streak", 0))
        history = raw.get("history")
        self.history = [dict(row) for row in history if isinstance(row, Mapping)][-64:] if isinstance(history, list) else []
        self.paradigm_attempts = Counter({str(k): int(v) for k, v in (raw.get("paradigm_attempts") or {}).items()})
        self.regime_attempts = Counter({str(k): int(v) for k, v in (raw.get("regime_attempts") or {}).items()})
        self.regime_improvements = Counter({str(k): int(v) for k, v in (raw.get("regime_improvements") or {}).items()})
        self.regime_trap_triggers = Counter({str(k): int(v) for k, v in (raw.get("regime_trap_triggers") or {}).items()})
        self.empirical_obstructed_regimes = {
            str(k): str(v) for k, v in (raw.get("empirical_obstructed_regimes") or {}).items()
        }
        self.steps_since_trigger = int(raw.get("steps_since_trigger", self.cooldown_steps))
        last = raw.get("last_directive")
        self.last_directive = ParadigmDirective(**last) if isinstance(last, Mapping) else None
