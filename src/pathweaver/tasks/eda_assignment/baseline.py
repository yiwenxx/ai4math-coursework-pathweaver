"""Seeded feasible matching followed by lexicographic local improvement.

The baseline is a heuristic, not a minimum-cost matching or optimality solver.
Its time budget is checked cooperatively; it does not isolate candidate code.
"""

from random import Random
from time import monotonic
from typing import Any, Mapping

from pathweaver.core.contracts import SolveBudget

from .evaluator import score_assignment
from .model import (
    SCHEMA_VERSION,
    TASK_ID,
    InfeasibleInstanceError,
    Instance,
    augmenting_matching,
    geometric_length,
    parse_instance,
)


BASELINE_NAME = "seeded_length_ordered_matching_lex_local_search_v1"


def _check_deadline(deadline: float) -> None:
    if monotonic() >= deadline:
        raise TimeoutError("EDA baseline exhausted wall budget before its initial score")


def _initial_assignment(
    instance: Instance, rng: Random, deadline: float
) -> tuple[dict[str, str], list[str], dict[str, list[str]]]:
    """Find a complete matching, preferring shorter sites along augmenting paths."""
    edges = list(instance.cross_edges)
    rng.shuffle(edges)
    edges.sort(key=lambda edge: len(edge.eligible_sites))
    preferences: dict[str, list[str]] = {}
    for edge in edges:
        _check_deadline(deadline)
        sites = list(edge.eligible_sites)
        rng.shuffle(sites)
        sites.sort(key=lambda site_id: geometric_length(instance, edge, site_id))
        preferences[edge.id] = sites
    order = [edge.id for edge in edges]
    assignment, hall_edges, _ = augmenting_matching(order, preferences)
    if hall_edges:
        raise InfeasibleInstanceError(("eligible sites do not admit a complete matching",))
    return assignment, order, preferences


def solve(
    instance: Mapping[str, Any], *, seed: int, budget: SolveBudget
) -> Mapping[str, Any]:
    """Return a capacity-one assignment within cooperative search budgets."""
    deadline = monotonic() + budget.wall_seconds
    parsed = parse_instance(instance)
    _check_deadline(deadline)
    assignment, order, preferences = _initial_assignment(parsed, Random(seed), deadline)
    _check_deadline(deadline)
    objectives = score_assignment(parsed, assignment)
    evaluations = 1
    eligibility = {edge_id: set(sites) for edge_id, sites in preferences.items()}

    def budget_reason() -> str | None:
        if monotonic() >= deadline:
            return "wall_budget"
        if evaluations >= budget.max_evaluations:
            return "evaluation_budget"
        return None

    termination: str | None = None
    while termination is None:
        termination = budget_reason()
        if termination is not None:
            break
        improved = False
        occupied = set(assignment.values())
        # A move is legal only if the destination site is currently unused.
        for edge_id in order:
            for site_id in preferences[edge_id]:
                termination = budget_reason()
                if termination is not None:
                    break
                if site_id in occupied:
                    continue
                previous = assignment[edge_id]
                assignment[edge_id] = site_id
                candidate = score_assignment(parsed, assignment)
                evaluations += 1
                if candidate < objectives:
                    objectives = candidate
                    improved = True
                    break
                assignment[edge_id] = previous
            if improved or termination is not None:
                break
        if termination is not None:
            break
        if improved:
            continue

        # Swaps preserve site capacity, but must satisfy both eligibility sets.
        for index, left in enumerate(order):
            for right_index in range(index + 1, len(order)):
                termination = budget_reason()
                if termination is not None:
                    break
                right = order[right_index]
                left_site, right_site = assignment[left], assignment[right]
                if right_site not in eligibility[left] or left_site not in eligibility[right]:
                    continue
                assignment[left], assignment[right] = right_site, left_site
                candidate = score_assignment(parsed, assignment)
                evaluations += 1
                if candidate < objectives:
                    objectives = candidate
                    improved = True
                    break
                assignment[left], assignment[right] = left_site, right_site
            if improved or termination is not None:
                break
        if termination is None and not improved:
            termination = "local_optimum"

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": parsed.instance_id,
        "solution": {"assignment": assignment},
        "metadata": {
            "baseline": BASELINE_NAME,
            "seed": seed,
            "evaluations": evaluations,
            "termination": termination,
        },
    }


def baseline(instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
    """TaskPack-compatible entry point using the budget's explicit random seed."""
    return solve(instance, seed=budget.seed, budget=budget)
