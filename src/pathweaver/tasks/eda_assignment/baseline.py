"""Seeded feasible matching followed by lexicographic local improvement.

The baseline is a heuristic, not a minimum-cost matching or optimality solver.
Its time budget is checked cooperatively; it does not isolate candidate code.
"""

from collections import deque
from math import isfinite
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
        lengths: dict[str, int] = {}
        for site_id in sites:
            _check_deadline(deadline)
            lengths[site_id] = geometric_length(instance, edge, site_id)
        sites.sort(key=lengths.__getitem__)
        preferences[edge.id] = sites

    assignment: dict[str, str] = {}
    owners: dict[str, str] = {}
    for root in edges:
        _check_deadline(deadline)
        queue = deque([root.id])
        predecessors: dict[str, tuple[str, str]] = {}
        seen_edges = {root.id}
        seen_sites: set[str] = set()
        endpoint: tuple[str, str] | None = None
        while queue and endpoint is None:
            edge_id = queue.popleft()
            for site_id in preferences[edge_id]:
                _check_deadline(deadline)
                if site_id in seen_sites:
                    continue
                seen_sites.add(site_id)
                owner = owners.get(site_id)
                if owner is None:
                    endpoint = (edge_id, site_id)
                    break
                if owner not in seen_edges:
                    seen_edges.add(owner)
                    predecessors[owner] = (edge_id, site_id)
                    queue.append(owner)
        if endpoint is None:
            raise InfeasibleInstanceError(("eligible sites do not admit a complete matching",))
        edge_id, site_id = endpoint
        while True:
            _check_deadline(deadline)
            assignment[edge_id] = site_id
            owners[site_id] = edge_id
            if edge_id == root.id:
                break
            edge_id, site_id = predecessors[edge_id]
    return assignment, [edge.id for edge in edges], preferences


def _validate_budget(seed: int, budget: SolveBudget) -> None:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if not isinstance(budget, SolveBudget):
        raise ValueError("budget must be a SolveBudget")
    if type(budget.max_evaluations) is not int or budget.max_evaluations < 1:
        raise ValueError("max_evaluations must be a positive integer")
    if type(budget.wall_seconds) not in (int, float):
        raise ValueError("wall_seconds must be finite and positive")
    try:
        valid_wall = isfinite(budget.wall_seconds) and budget.wall_seconds > 0
    except OverflowError:
        valid_wall = False
    if not valid_wall:
        raise ValueError("wall_seconds must be finite and positive")


def solve(
    instance: Mapping[str, Any], *, seed: int, budget: SolveBudget
) -> Mapping[str, Any]:
    """Return a capacity-one assignment within cooperative search budgets.

    Every full-DAG score, including the initial one, consumes one evaluation.
    Seeded traversal is reproducible when the wall deadline does not intervene.
    Parsing and matching count towards elapsed time. If they consume the time
    budget before an incumbent can be scored, raise ``TimeoutError``. Once an
    incumbent is scored, budget exhaustion returns the best assignment so far.
    """
    _validate_budget(seed, budget)
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
    if not isinstance(budget, SolveBudget):
        raise ValueError("budget must be a SolveBudget")
    return solve(instance, seed=budget.seed, budget=budget)
