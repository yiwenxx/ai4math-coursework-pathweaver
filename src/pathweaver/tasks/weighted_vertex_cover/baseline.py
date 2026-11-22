"""Weighted greedy + local-improvement baseline and tiny exact branch-and-bound solver."""
from collections.abc import Mapping
from random import Random
from time import monotonic
from typing import Any

from pathweaver.core.contracts import SolveBudget
from .model import SCHEMA_VERSION, TASK_ID, parse_instance


def _prune_redundant(selected: set[str], weights: Mapping[str, int], adj: Mapping[str, tuple[str, ...]]) -> None:
    for vid in sorted(selected, key=lambda v: (-weights[v], v)):
        if all(nb in selected for nb in adj[vid]):
            selected.remove(vid)


def solve(instance_raw: Mapping[str, Any], budget: SolveBudget) -> dict[str, Any]:
    instance = parse_instance(instance_raw)
    deadline = monotonic() + budget.wall_seconds
    rng = Random(budget.seed)
    weights = instance.weights
    adj = instance.adjacency

    # 1. Weighted greedy by cost-per-newly-covered-edge.
    selected: set[str] = set()
    uncovered = set(instance.edges)
    while uncovered:
        degree = {v: 0 for v in instance.vertex_ids}
        for u, v in uncovered:
            degree[u] += 1
            degree[v] += 1
        candidates = [v for v in instance.vertex_ids if degree[v] > 0]
        # Minimize weight / degree (using exact integer cross-comparison via float tuple + tie-break).
        best = min(candidates, key=lambda v: (weights[v] / degree[v], weights[v], v))
        selected.add(best)
        uncovered = {e for e in uncovered if best not in e}
    _prune_redundant(selected, weights, adj)

    best_selected = set(selected)
    best_weight = sum(weights[v] for v in best_selected)
    evaluations = 1

    # 2. Local improvement: try dropping one expensive vertex and covering its exposed neighbors.
    improved = True
    while improved and evaluations < budget.max_evaluations and monotonic() < deadline:
        improved = False
        order = sorted(best_selected, key=lambda v: (-weights[v], rng.random()))
        for vid in order:
            if evaluations >= budget.max_evaluations or monotonic() >= deadline:
                break
            needed = [nb for nb in adj[vid] if nb not in best_selected]
            replacement_weight = sum(weights[nb] for nb in needed)
            evaluations += 1
            if replacement_weight < weights[vid]:
                candidate = (best_selected - {vid}) | set(needed)
                _prune_redundant(candidate, weights, adj)
                cand_weight = sum(weights[v] for v in candidate)
                if cand_weight < best_weight:
                    best_selected = candidate
                    best_weight = cand_weight
                    improved = True
                    break

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": instance.instance_id,
        "solution": {"selected_vertices": sorted(best_selected)},
        "metadata": {"strategy": "weighted_greedy_local_v1", "evaluations": evaluations, "seed": budget.seed},
    }


def exact_solve(instance_raw: Mapping[str, Any], budget: SolveBudget, *, emit_certificate: bool = True) -> dict[str, Any]:
    """Exact branch-and-bound reference solver for tiny instances (n <= 28), optionally emitting a BnB proof tree."""
    instance = parse_instance(instance_raw)
    if len(instance.vertex_ids) > 28:
        raise ValueError("exact_solve is restricted to tiny reference instances with at most 28 vertices")
    deadline = monotonic() + budget.wall_seconds
    weights = instance.weights
    adj = instance.adjacency
    # Warm-start upper bound from baseline.
    seed_sol = solve(instance_raw, budget)
    best_set = set(seed_sol["solution"]["selected_vertices"])
    best_weight = sum(weights[v] for v in best_set)
    edges = list(instance.edges)
    nodes_visited = 0
    timed_out = False

    def search(idx: int, current: set[str], excluded: set[str], current_weight: int) -> dict[str, Any] | None:
        nonlocal best_set, best_weight, nodes_visited, timed_out
        if current_weight >= best_weight:
            return {"kind": "pruned_by_bound"} if emit_certificate else None
        nodes_visited += 1
        if nodes_visited % 512 == 0 and monotonic() >= deadline:
            timed_out = True
            return None
        while idx < len(edges) and (edges[idx][0] in current or edges[idx][1] in current):
            idx += 1
        if idx == len(edges):
            best_set = set(current)
            best_weight = current_weight
            return {"kind": "incumbent", "selected_vertices": sorted(current)} if emit_certificate else None
        u, v = edges[idx]
        first, second = (u, v) if weights[u] <= weights[v] else (v, u)
        if first in excluded:
            # Forced to include second (or pick valid branch var).
            first, second = second, first
        if first in excluded:
            return {"kind": "infeasible"} if emit_certificate else None

        # Branch 1: include `first`.
        current.add(first)
        inc_node = search(idx + 1, current, excluded, current_weight + weights[first])
        current.remove(first)
        if timed_out:
            return None

        # Branch 2: exclude `first` -> must include all uncovered neighbors of `first`.
        forced = [nb for nb in adj[first] if nb not in current]
        if any(nb in excluded for nb in forced):
            exc_node = {"kind": "infeasible"} if emit_certificate else None
        else:
            add_w = sum(weights[nb] for nb in forced)
            if current_weight + add_w >= best_weight:
                exc_node = {"kind": "pruned_by_bound"} if emit_certificate else None
            else:
                excluded.add(first)
                for nb in forced:
                    current.add(nb)
                exc_node = search(idx + 1, current, excluded, current_weight + add_w)
                for nb in forced:
                    current.remove(nb)
                excluded.remove(first)
        if timed_out:
            return None
        if emit_certificate and inc_node is not None and exc_node is not None:
            return {"kind": "branch", "var": first, "include": inc_node, "exclude": exc_node}
        return None

    tree = search(0, set(), set(), 0)
    completed_first_pass = not timed_out
    cert_tree = tree if completed_first_pass else None
    # Note: if best_set came strictly from warm-start and no leaf beat it, emit leaf check on exact incumbent.
    # To keep proof tree guaranteed to contain at least one `incumbent` leaf attaining `best_weight`:
    if emit_certificate and completed_first_pass and cert_tree is not None:
        def _has_attaining_incumbent(node: dict[str, Any]) -> bool:
            k = node.get("kind")
            if k == "incumbent":
                return sum(weights[v] for v in node["selected_vertices"]) == best_weight
            if k == "branch":
                return _has_attaining_incumbent(node["include"]) or _has_attaining_incumbent(node["exclude"])
            return False

        if not _has_attaining_incumbent(cert_tree):
            # Re-run strict search from upper bound best_weight + 1 so optimal leaf is explicitly emitted.
            saved_weight = best_weight
            saved_set = set(best_set)
            best_weight = saved_weight + 1
            nodes_visited = 0
            rerun_tree = search(0, set(), set(), 0)
            if timed_out or rerun_tree is None:
                best_weight = saved_weight
                best_set = saved_set
                cert_tree = None
            else:
                cert_tree = rerun_tree

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": instance.instance_id,
        "solution": {"selected_vertices": sorted(best_set)},
        "metadata": {
            "strategy": "exact_branch_and_bound",
            "nodes_visited": nodes_visited,
            "completed_search": completed_first_pass,
        },
    }
    if emit_certificate and completed_first_pass and cert_tree is not None:
        out["optimality_certificate"] = {"schema_version": 1, "method": "bnb_proof_tree", "tree": cert_tree}
    return out
