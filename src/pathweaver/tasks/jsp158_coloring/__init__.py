"""Finite AP-coloring TaskPack for JSP-000158 / Erdős problem 160."""
from pathweaver.core.contracts import SolveBudget

from .evaluator import evaluate
from .model import MAX_N, TASK_ID, InvalidInstanceError, generate, parse_instance


class Jsp158ColoringTaskPack:
    task_id = TASK_ID

    def describe(self):
        return {"task_id": TASK_ID, "schema_version": 1, "status": "implemented",
                "problem": "JSP-000158 / Erdos #160", "objectives": ["min_color_count"],
                "constraints": ["every four-term AP in [1,N] uses at least three colors"],
                "decision_space": "N integer labels in [0,N-1]", "max_n": MAX_N,
                "baseline": "all-distinct fallback with validity-preserving recoloring",
                "budget_unit": "attempted single-position recolorings; cooperative wall clock",
                "dataset_status": "fixed parameter illustrations, not a research benchmark",
                "evidence_scope": "finite construction; no optimality or asymptotic claim"}

    def generate(self, *, seed, size):
        return generate(seed=seed, size=size)

    def validate_instance(self, instance):
        try:
            parse_instance(instance)
        except InvalidInstanceError as error:
            return error.violations
        return ()

    def verify(self, instance, solution):
        return evaluate(instance, solution)

    def baseline(self, instance, budget: SolveBudget):
        parse_instance(instance)
        from .discovery_seed import solve

        return solve(instance, {"wall_seconds": budget.wall_seconds, "seed": budget.seed,
                                "max_evaluations": budget.max_evaluations})


__all__ = ["Jsp158ColoringTaskPack", "InvalidInstanceError", "evaluate", "generate", "parse_instance"]
