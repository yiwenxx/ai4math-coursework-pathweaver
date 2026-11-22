"""Weighted minimum vertex cover TaskPack (required transfer case)."""
from collections.abc import Mapping, Sequence
from typing import Any

from pathweaver.core.contracts import Evaluation, SolveBudget
from .baseline import exact_solve, solve
from .evaluator import evaluate
from .generator import generate_instance
from .model import SCHEMA_VERSION, TASK_ID, parse_instance


class WeightedVertexCoverTaskPack:
    task_id = TASK_ID

    def describe(self) -> Mapping[str, Any]:
        return {
            "task_id": TASK_ID,
            "schema_version": SCHEMA_VERSION,
            "scope": "required_transfer",
            "objectives": ("min_selected_weight",),
            "decision_structure": "subset_selection_covering_constraints",
        }

    def generate(self, *, seed: int, size: int) -> Mapping[str, Any]:
        return generate_instance(seed=seed, size=size)

    def validate_instance(self, instance: Mapping[str, Any]) -> Sequence[str]:
        try:
            parse_instance(instance)
        except ValueError as error:
            return (str(error),)
        return ()

    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation:
        return evaluate(instance, solution)

    def baseline(self, instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
        return solve(instance, budget)

    def exact(self, instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
        return exact_solve(instance, budget)


__all__ = ["WeightedVertexCoverTaskPack", "evaluate", "exact_solve", "generate_instance", "parse_instance", "solve"]
