"""Runnable EDA TaskPack with trusted feasibility and objective recomputation."""
from typing import Any, Mapping, Sequence

from pathweaver.core.contracts import Evaluation, SolveBudget

from .evaluator import evaluate
from .generator import generate
from .model import TASK_ID, InvalidInstanceError, InfeasibleInstanceError, parse_instance


def compare_objectives(left: tuple[int, int], right: tuple[int, int]) -> int:
    """Return -1, 0 or 1 for better, equal or worse exact (T, L) objectives."""
    for objective in (left, right):
        if not isinstance(objective, tuple) or len(objective) != 2:
            raise ValueError("EDA objectives must be (T, L) tuples")
        if any(type(value) is not int or value < 0 for value in objective):
            raise ValueError("EDA objectives must be nonnegative integers")
    return (left > right) - (left < right)


class EdaAssignmentTaskPack:
    """Domain implementation of the shared core.contracts.TaskPack protocol."""

    task_id = TASK_ID

    def describe(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "schema_version": 1,
            "status": "implemented",
            "objectives": ["min_longest_path", "min_cross_tier_geometric_length"],
            "ordering": "lexicographic (T, L), exact nonnegative integers",
            "constraints": [
                "DAG with fixed integer coordinates and nonnegative integer tiers",
                "exactly one eligible site per cross-tier edge",
                "global capacity one per site",
                "same-tier edges have fixed nonnegative integer delay",
            ],
            "decision_space": "finite injective edge-to-eligible-site assignments",
            "baseline": "seeded length-ordered matching with lexicographic local descent",
            "alternative_strategies": ["path-matching: full-DAG path guidance and minimum-cost capacity matching"],
            "budget_unit": "full-DAG objective evaluations, including the initial assignment",
            "wall_budget": "cooperative deadline; no execution isolation",
            "generator_size": "number of cross-tier edges",
            "lower_bound": "ignore site contention; minimize each cross-edge length",
            "dataset_status": "hand-authored examples and public Bookshelf/Open3DBench case adapters",
        }

    def generate(self, *, seed: int, size: int) -> Mapping[str, Any]:
        return generate(seed=seed, size=size)

    def validate_instance(self, instance: Mapping[str, Any]) -> Sequence[str]:
        """Return instance errors; parse_instance preserves their error category."""
        try:
            parse_instance(instance)
        except InvalidInstanceError as error:
            return error.violations
        return ()

    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation:
        return evaluate(instance, solution)

    def baseline(self, instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
        # Verification never imports or executes candidate solver code.
        from .baseline import baseline

        return baseline(instance, budget)


__all__ = [
    "EdaAssignmentTaskPack", "InvalidInstanceError", "InfeasibleInstanceError",
    "compare_objectives", "evaluate", "generate", "parse_instance",
]
