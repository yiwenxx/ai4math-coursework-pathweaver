"""Independent feasibility and full-DAG objective evaluation.

No baseline, candidate score, diagnostic, or claimed certificate is trusted.
"""
from collections.abc import Mapping
from typing import Any

from pathweaver.core.contracts import Evaluation, EvidenceLevel
from .certificate import check_certificate
from .model import Instance, SCHEMA_VERSION, TASK_ID, geometric_length, parse_instance


def _assignment_violations(instance: Instance, solution: Any) -> tuple[dict[str, str], tuple[str, ...]]:
    violations: list[str] = []
    if not isinstance(solution, Mapping):
        return {}, ("solution must be an object",)
    version = solution.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version != SCHEMA_VERSION:
        violations.append(f"solution.schema_version must be {SCHEMA_VERSION}")
    if solution.get("task_id") != TASK_ID:
        violations.append(f"solution.task_id must be {TASK_ID!r}")
    if solution.get("instance_id") != instance.instance_id:
        violations.append("solution.instance_id does not match the instance")
    payload = solution.get("solution")
    if not isinstance(payload, Mapping):
        return {}, (*violations, "solution.solution must be an object")
    assignment = payload.get("assignment")
    if not isinstance(assignment, Mapping):
        return {}, (*violations, "solution.assignment must be an object mapping edge IDs to site IDs")
    cross = {edge.id: edge for edge in instance.cross_edges}
    for edge_id in sorted(cross.keys() - assignment.keys()):
        violations.append(f"assignment missing cross-tier edge {edge_id!r}")
    for edge_id in sorted(assignment.keys() - cross.keys(), key=str):
        violations.append(f"assignment contains a non-cross-tier or unknown edge {edge_id!r}")
    occupied: dict[str, str] = {}
    for edge_id, site_id in assignment.items():
        if not isinstance(site_id, str) or site_id not in instance.sites:
            violations.append(f"assignment[{edge_id!r}] must reference an existing site")
            continue
        if edge_id in cross and site_id not in cross[edge_id].eligible_sites:
            violations.append(f"site {site_id!r} is ineligible for edge {edge_id!r}")
        if site_id in occupied:
            violations.append(
                f"site {site_id!r} exceeds capacity one: edges {occupied[site_id]!r} and {edge_id!r}"
            )
        else:
            occupied[site_id] = edge_id
    if violations:
        return {}, tuple(violations)
    return dict(assignment), ()


def _weights(instance: Instance, assignment: Mapping[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    delays: dict[str, int] = {}
    lengths: dict[str, int] = {}
    for edge in instance.edges:
        if edge.delay is not None:
            delays[edge.id] = edge.delay
        else:
            length = geometric_length(instance, edge, assignment[edge.id])
            lengths[edge.id] = length
            delays[edge.id] = edge.base_delay + edge.alpha * length
    return delays, lengths


def _arrival_times(
    instance: Instance, delays: Mapping[str, int], outgoing: Mapping[str, list[Any]] | None = None
) -> tuple[dict[str, int], dict[str, str]]:
    outgoing = outgoing or instance.outgoing()
    arrival = dict.fromkeys(instance.nodes, 0)
    predecessor: dict[str, str] = {}
    for node in instance.topological_order:
        for edge in outgoing[node]:
            candidate = arrival[node] + delays[edge.id]
            if candidate > arrival[edge.target] or (
                candidate == arrival[edge.target]
                and (edge.target not in predecessor or edge.id < predecessor[edge.target])
            ):
                arrival[edge.target] = candidate
                predecessor[edge.target] = edge.id
    return arrival, predecessor


def score_assignment(instance: Instance, assignment: Mapping[str, str]) -> tuple[int, int]:
    """Score an already-feasible assignment; recompute every edge and DAG arrival."""
    delays, lengths = _weights(instance, assignment)
    arrivals, _ = _arrival_times(instance, delays)
    return max(arrivals.values()), sum(lengths.values())


def _remaining_times(
    instance: Instance, delays: Mapping[str, int], outgoing: Mapping[str, list[Any]] | None = None
) -> dict[str, int]:
    outgoing = outgoing or instance.outgoing()
    remaining = dict.fromkeys(instance.nodes, 0)
    for node in reversed(instance.topological_order):
        remaining[node] = max(
            (delays[edge.id] + remaining[edge.target] for edge in outgoing[node]), default=0,
        )
    return remaining


def evaluate(instance_mapping: Mapping[str, Any], solution_mapping: Mapping[str, Any]) -> Evaluation:
    """Raise instance errors; return infeasible Evaluation for any invalid solution."""
    instance = parse_instance(instance_mapping)
    assignment, violations = _assignment_violations(instance, solution_mapping)
    if violations:
        return Evaluation(
            feasible=False, objectives=None, violations=violations,
            diagnostics={"failure_kind": "invalid_solution"},
        )
    outgoing = instance.outgoing()
    by_id = {edge.id: edge for edge in instance.edges}
    delays, lengths = _weights(instance, assignment)
    arrivals, predecessor = _arrival_times(instance, delays, outgoing)
    total_delay, total_length = max(arrivals.values()), sum(lengths.values())
    remaining = _remaining_times(instance, delays, outgoing)
    slack = {
        edge.id: total_delay - arrivals[edge.source] - delays[edge.id] - remaining[edge.target]
        for edge in instance.edges
    }
    sinks = [node for node in instance.nodes if not outgoing[node]]
    end = min(node for node in sinks if arrivals[node] == total_delay)
    critical_path: list[str] = []
    while end in predecessor:
        edge = by_id[predecessor[end]]
        critical_path.append(edge.id)
        end = edge.source
    critical_path.reverse()

    relaxed_lengths = {
        edge.id: min(geometric_length(instance, edge, site) for site in edge.eligible_sites)
        for edge in instance.cross_edges
    }
    relaxed_delays = {
        edge.id: edge.delay if edge.delay is not None
        else edge.base_delay + edge.alpha * relaxed_lengths[edge.id]
        for edge in instance.edges
    }
    relaxed_arrivals, _ = _arrival_times(instance, relaxed_delays, outgoing)
    lower_bound = (max(relaxed_arrivals.values()), sum(relaxed_lengths.values()))
    objectives = (total_delay, total_length)
    attained = objectives == lower_bound
    certificate = check_certificate(
        instance, assignment, solution_mapping.get("optimality_certificate"),
        objectives=objectives, lower_bound=lower_bound, relaxed_arrivals=relaxed_arrivals,
        relaxed_remaining=(_remaining_times(instance, relaxed_delays, outgoing)
                           if solution_mapping.get("optimality_certificate") is not None else {}),
    )
    certified = certificate["status"] == "verified"
    occupant = {site: edge for edge, site in assignment.items()}
    diagnostics = {
        "arrivals": arrivals,
        "remaining_to_sink": remaining,
        "edge_slack": slack,
        "edges": {
            edge.id: {
                "source": edge.source, "target": edge.target,
                "delay": delays[edge.id], "slack": slack[edge.id],
                "length": lengths.get(edge.id), "site": assignment.get(edge.id),
            }
            for edge in instance.edges
        },
        "critical_edges": sorted(edge for edge, value in slack.items() if value == 0),
        "critical_path": critical_path,
        "site_contention": {
            site: {
                "capacity": 1,
                "eligible_edges": sorted(edge.id for edge in instance.cross_edges if site in edge.eligible_sites),
                "assigned_edge": occupant.get(site),
            }
            for site in sorted(instance.sites)
        },
        "lower_bound_method": "independent_minimum_lengths_ignoring_site_capacity",
        "lower_bound_attained": attained,
        "optimality_certificate": certificate,
        "optimality_method": ("relaxed_path_matching_duality" if certified
                              else "independent_coordinate_lower_bounds" if attained else None),
    }
    return Evaluation(
        feasible=True, objectives=objectives, diagnostics=diagnostics, lower_bound=lower_bound,
        evidence=EvidenceLevel.FINITE_OPTIMAL if attained or certified else EvidenceLevel.EXPERIMENTAL,
    )
