"""Trusted JSP-000158 discovery admission, exact bounds and failure feedback."""
from collections.abc import Mapping
from dataclasses import asdict
from random import Random
from typing import Any

from .evaluator import evaluate, evaluate_prepared, prepare_verifier
from .model import SCHEMA_VERSION, TASK_ID, generate, parse_instance


class Jsp158DiscoveryTask:
    task_id = TASK_ID

    def prepare(self, raw):
        instance = parse_instance(raw)
        # Rebuild, rather than forwarding mutable metadata or reference solutions.
        return {"schema_version": SCHEMA_VERSION, "task_id": TASK_ID,
                "instance_id": instance.instance_id, "data": {"n": instance.n}}

    def objective_domain(self, raw):
        return (parse_instance(raw).n,), (1,)

    def prepare_verifier(self, instance):
        return prepare_verifier(instance)

    def verify_prepared(self, prepared, solution, *, parent_solution=None):
        return evaluate_prepared(
            prepared,
            solution,
            parent_solution=parent_solution,
            parent_verified=(parent_solution is not None),
        )

    def verify(self, instance, solution):
        return evaluate(instance, solution)

    def paradigm_catalog(self):
        return (
            {
                "id": "algebraic_modular_group",
                "regime": "algebraic_modular_group",
                "title": "Product / Base-m Quotient + ABBA-Free Modular Template Construction",
                "mechanism": "Construct colorings via digits in base m combined with a small ABBA-free modular table and carry-control residue labels, or non-additive coupled permutations rather than single-point greedy recoloring.",
                "anti_pattern": "Do not perform single-position greedy recoloring descent alone or cubic-norm + Frobenius linear perturbation (known obstructed in restricted families).",
            },
            {
                "id": "constraint_propagation_backtracking",
                "regime": "exact_branch_and_reduce",
                "title": "Symmetry-Broken Backtracking / Conflict-Guided DSATUR Coloring",
                "mechanism": "Maintain per-position forbidden-color bitmasks implied by 3-term pairs of 4-APs (unit propagation on 2-color hazards), branching on most-constrained integers.",
                "anti_pattern": "Do not greedily merge colors without propagating forced 4-AP bans.",
            },
            {
                "id": "lns_ap_destroy_repair",
                "regime": "metaheuristic_population",
                "title": "Violation-Focused Large-Neighborhood Destroy-and-Repair",
                "mechanism": "Destroy 20-35% of positions participating in the largest color-class conflicts or tightest 4-AP bottlenecks and recolor via randomized backtracking or Kempe-style multi-position swaps.",
                "anti_pattern": "Do not restrict search to monotonic 1-position recolors.",
            },
        )

    def certificate(self, instance, solution, result):
        cert = result.diagnostics.get("optimality_certificate") if isinstance(result.diagnostics, dict) else None
        if not result.feasible or not isinstance(cert, dict) or cert.get("status") != "verified":
            return None
        return {
            "schema_version": 1,
            "kind": f"jsp158_{result.evidence.value}_certificate",
            "instance": instance,
            "solution": solution,
            "verification": asdict(result),
        }

    def reduce_instance(self, instance, evaluation, *, max_size=32):
        """Shrink interval length N while keeping a valid [1, N] JSP-000158 instance."""
        inst = parse_instance(instance)
        if inst.n <= 12:
            return None
        diag = (evaluation.get("diagnostics") or {}) if isinstance(evaluation, dict) else {}
        target_n = None
        if not evaluation.get("feasible") and diag.get("violating_progressions"):
            progs = [p for p in diag["violating_progressions"] if isinstance(p, (list, tuple)) and p]
            if progs:
                cand = max(int(x) for p in progs for x in p)
                if 4 <= cand < inst.n:
                    target_n = cand
        if target_n is None:
            cand = max(12, min(inst.n - 4, max(int(max_size), inst.n // 2)))
            if 4 <= cand < inst.n:
                target_n = cand
        if target_n is None:
            return None
        raw_reduced = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__diag_n{int(target_n)}",
            "data": {"n": int(target_n)},
        }
        try:
            parse_instance(raw_reduced)
        except ValueError:
            return None
        return self.prepare(raw_reduced)

    def permute_instance(self, instance: Mapping[str, Any], *, seed: int = 1) -> dict[str, Any]:
        """Return an isomorphic JSP-000158 instance with an unseen instance_id and identical N."""
        inst = parse_instance(instance)
        raw_perm = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__iso_{seed}",
            "data": {"n": inst.n},
        }
        return self.prepare(raw_perm)

    def generate_adversarial_instances(self, *, seed: int, count: int = 2) -> list[dict[str, Any]]:
        """Generate unseen small JSP-000158 instances (size 8-16) for active adversarial probing."""
        rng = Random(seed)
        results: list[dict[str, Any]] = []
        for idx in range(max(0, int(count))):
            size = 8 + rng.randrange(9)
            sub_seed = seed * 1009 + idx * 97 + 17
            raw = dict(generate(seed=sub_seed, size=size))
            raw["instance_id"] = f"jsp158-adv-n{size}-s{seed}-{idx}"
            results.append(self.prepare(raw))
        return results

    def feedback(self, result):
        diagnostics = result.diagnostics
        return {"feasible": result.feasible, "objectives": result.objectives,
                "violations": list(result.violations)[:4], "lower_bound": result.lower_bound,
                "n": diagnostics.get("n"), "color_count": diagnostics.get("color_count"),
                "violation_count": diagnostics.get("violation_count"),
                "violating_progressions": diagnostics.get("violating_progressions", [])[:3],
                "color_class_sizes": diagnostics.get("color_class_sizes", [])[:8]}

    def brief(self):
        return '''Implement a standalone standard-library Python function solve(instance, budget) returning a JSON object.
Task: JSP-000158, corresponding to Erdos problem 160 (not Erdos problem 158).
The input has schema_version=1, task_id="jsp158_coloring", instance_id, data={"n":N}.
Color ALL integers 1,...,N. Return {"schema_version":1,"task_id":"jsp158_coloring",
"instance_id":instance["instance_id"],"solution":{"colors":[N integer labels]}}.
colors[i] colors integer i+1. Labels must be integers in [0,N-1], not booleans.
For EVERY a>=1,d>=1 with a+3*d<=N, the four labels at a,a+d,a+2*d,a+3*d
must contain AT LEAST THREE DISTINCT COLORS. Both monochromatic and two-color progressions are invalid.
Minimize the actual number of distinct labels, not max(label)+1. Holes in labels are allowed.
The host independently enumerates every four-term arithmetic progression and recomputes color count.
Candidate-reported scores and claims are ignored. Invalid colorings have zero search score.
budget contains wall_seconds and seed. No pathweaver or third-party modules are installed.
Keep a legal fallback (all distinct labels works), and preserve validity when merging colors or recoloring.
Use seeded choices and bounded work, returning a legal best coloring before the time limit. Do not print.
Improve the CONSTRUCTION ALGORITHM across sizes; do not memorize IDs or hard-code the training solutions.
Feedback includes violating arithmetic progressions, color patterns and color class sizes.
Finite colorings give upper bounds on h(N), not optimality, asymptotic theorems or Lean proofs.
'''
