"""Independent feasibility and full-DAG objective evaluation (with compiled instance caching).

No baseline, candidate score, diagnostic, or claimed certificate is trusted.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pathweaver.core.contracts import Evaluation, EvidenceLevel, validate_solution_envelope
from .certificate import check_certificate
from .model import Instance, SCHEMA_VERSION, TASK_ID, geometric_length, parse_instance


def _assignment_violations(instance: Instance, solution: Any) -> tuple[dict[str, str], tuple[str, ...]]:
    payload, violations = validate_solution_envelope(
        solution, task_id=TASK_ID, instance_id=instance.instance_id, schema_version=SCHEMA_VERSION,
    )
    if payload is None:
        return {}, tuple(violations)
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


@dataclass(frozen=True)
class PreparedEdaInstance:
    """Immutable host-side compiled representation avoiding per-candidate parsing and lower-bound recomputation."""

    instance: Instance
    node_ids: tuple[str, ...]
    node_idx: dict[str, int]
    edge_ids: tuple[str, ...]
    edge_src: tuple[int, ...]
    edge_dst: tuple[int, ...]
    outgoing_idx: tuple[tuple[tuple[int, int], ...], ...]
    sink_indices: tuple[int, ...]
    fixed_delays: list[int | None]
    cross_indices: tuple[int, ...]
    cross_ids: tuple[str, ...]
    cross_lengths: dict[int, dict[str, int]]
    relaxed_arrivals: dict[str, int]
    relaxed_remaining: dict[str, int]
    lower_bound: tuple[int, int]


def prepare_verifier(instance_mapping: Mapping[str, Any]) -> PreparedEdaInstance:
    """Parse instance once and compile flat topological arrays and relaxed DAG bounds."""
    instance = parse_instance(instance_mapping)
    node_ids = instance.topological_order
    node_idx = {nid: i for i, nid in enumerate(node_ids)}
    outgoing = instance.outgoing()
    edge_ids = tuple(e.id for e in instance.edges)
    edge_src = tuple(node_idx[e.source] for e in instance.edges)
    edge_dst = tuple(node_idx[e.target] for e in instance.edges)
    outgoing_lists: list[list[tuple[int, int]]] = [[] for _ in node_ids]
    fixed_delays: list[int | None] = []
    cross_indices: list[int] = []
    cross_lengths: dict[int, dict[str, int]] = {}
    relaxed_lengths: dict[str, int] = {}
    relaxed_delays: dict[str, int] = {}

    for e_i, edge in enumerate(instance.edges):
        outgoing_lists[edge_src[e_i]].append((e_i, edge_dst[e_i]))
        if edge.delay is not None:
            fixed_delays.append(edge.delay)
            relaxed_delays[edge.id] = edge.delay
        else:
            fixed_delays.append(None)
            cross_indices.append(e_i)
            l_map = {s: geometric_length(instance, edge, s) for s in edge.eligible_sites}
            cross_lengths[e_i] = l_map
            min_len = min(l_map.values())
            relaxed_lengths[edge.id] = min_len
            relaxed_delays[edge.id] = edge.base_delay + edge.alpha * min_len

    outgoing_idx = tuple(tuple(row) for row in outgoing_lists)
    sink_indices = tuple(i for i, row in enumerate(outgoing_idx) if not row)
    relaxed_arrivals, _ = _arrival_times(instance, relaxed_delays, outgoing)
    relaxed_remaining = _remaining_times(instance, relaxed_delays, outgoing)
    lower_bound = (max(relaxed_arrivals.values()), sum(relaxed_lengths.values()))
    return PreparedEdaInstance(
        instance=instance,
        node_ids=node_ids,
        node_idx=node_idx,
        edge_ids=edge_ids,
        edge_src=edge_src,
        edge_dst=edge_dst,
        outgoing_idx=outgoing_idx,
        sink_indices=sink_indices,
        fixed_delays=fixed_delays,
        cross_indices=tuple(cross_indices),
        cross_ids=tuple(edge_ids[i] for i in cross_indices),
        cross_lengths=cross_lengths,
        relaxed_arrivals=relaxed_arrivals,
        relaxed_remaining=relaxed_remaining,
        lower_bound=lower_bound,
    )


def evaluate_prepared(
    prepared: PreparedEdaInstance,
    solution_mapping: Mapping[str, Any],
    *,
    include_edge_details: bool = True,
) -> Evaluation:
    """Independently check feasibility and full-DAG objectives using compiled topology."""
    instance = prepared.instance
    assignment, violations = _assignment_violations(instance, solution_mapping)
    if violations:
        return Evaluation(
            feasible=False, objectives=None, violations=violations,
            diagnostics={"failure_kind": "invalid_solution"},
            lower_bound=prepared.lower_bound,
        )

    n_nodes = len(prepared.node_ids)
    delays = list(prepared.fixed_delays)
    total_length = 0
    edge_lengths: dict[str, int] = {}
    for e_i in prepared.cross_indices:
        edge = instance.edges[e_i]
        site_id = assignment[edge.id]
        length = prepared.cross_lengths[e_i][site_id]
        total_length += length
        delays[e_i] = edge.base_delay + edge.alpha * length
        if include_edge_details:
            edge_lengths[edge.id] = length

    arrival_arr = [0] * n_nodes
    pred_edge = [-1] * n_nodes
    edge_ids = prepared.edge_ids
    for u_i, arcs in enumerate(prepared.outgoing_idx):
        au = arrival_arr[u_i]
        for e_i, v_i in arcs:
            cand = au + delays[e_i]  # type: ignore[operator]
            cur = arrival_arr[v_i]
            if cand > cur or (cand == cur and (pred_edge[v_i] == -1 or edge_ids[e_i] < edge_ids[pred_edge[v_i]])):
                arrival_arr[v_i] = cand
                pred_edge[v_i] = e_i

    total_delay = max(arrival_arr)
    remaining_arr = [0] * n_nodes
    for u_i in range(n_nodes - 1, -1, -1):
        arcs = prepared.outgoing_idx[u_i]
        if arcs:
            remaining_arr[u_i] = max(delays[e_i] + remaining_arr[v_i] for e_i, v_i in arcs)  # type: ignore[operator]

    end_idx = min(
        (i for i in prepared.sink_indices if arrival_arr[i] == total_delay),
        key=lambda i: prepared.node_ids[i],
    )
    critical_path: list[str] = []
    cur_idx = end_idx
    while pred_edge[cur_idx] != -1:
        e_i = pred_edge[cur_idx]
        critical_path.append(edge_ids[e_i])
        cur_idx = prepared.edge_src[e_i]
    critical_path.reverse()

    objectives = (total_delay, total_length)
    lower_bound = prepared.lower_bound
    attained = objectives == lower_bound
    raw_cert = solution_mapping.get("optimality_certificate")
    certificate = check_certificate(
        instance, assignment, raw_cert,
        objectives=objectives, lower_bound=lower_bound,
        relaxed_arrivals=prepared.relaxed_arrivals,
        relaxed_remaining=prepared.relaxed_remaining if raw_cert is not None else {},
    )
    certified = certificate["status"] == "verified"
    cert_evidence = certificate.get("evidence")
    if attained or (certified and cert_evidence == "finite_optimal"):
        evidence = EvidenceLevel.FINITE_OPTIMAL
        if certified and "T_lower_bound" in certificate:
            lower_bound = (max(lower_bound[0], int(certificate["T_lower_bound"])), lower_bound[1])
    elif certified and cert_evidence == "certified_bound":
        evidence = EvidenceLevel.CERTIFIED_BOUND
        lower_bound = (max(lower_bound[0], int(certificate["T_lower_bound"])), lower_bound[1])
    else:
        evidence = EvidenceLevel.EXPERIMENTAL

    edge_src = prepared.edge_src
    edge_dst = prepared.edge_dst
    crit_set = set(critical_path[:12]) if not include_edge_details else None
    slack: dict[str, int] = {}
    edges_diag: dict[str, dict[str, Any]] = {}
    critical_edges_list: list[str] = []
    for e_i, edge in enumerate(instance.edges):
        sl = total_delay - arrival_arr[edge_src[e_i]] - delays[e_i] - remaining_arr[edge_dst[e_i]]  # type: ignore[operator]
        if sl == 0:
            critical_edges_list.append(edge.id)
        if include_edge_details:
            slack[edge.id] = sl
        if include_edge_details or edge.id in crit_set:  # type: ignore[operator]
            edges_diag[edge.id] = {
                "source": edge.source, "target": edge.target,
                "delay": delays[e_i], "slack": sl,
                "length": (edge_lengths.get(edge.id) if include_edge_details
                           else (prepared.cross_lengths[e_i][assignment[edge.id]] if e_i in prepared.cross_lengths else None)),
                "site": assignment.get(edge.id),
            }

    diagnostics: dict[str, Any] = {
        "critical_edges": sorted(critical_edges_list),
        "critical_path": critical_path,
        "edges": edges_diag,
        "lower_bound_method": "independent_minimum_lengths_ignoring_site_capacity",
        "relaxed_lower_bound": list(prepared.lower_bound),
        "lower_bound_attained": attained,
        "optimality_certificate": certificate,
        "optimality_method": (certificate.get("method") if certified
                              else "independent_coordinate_lower_bounds" if attained else None),
    }
    if include_edge_details:
        occupant = {site: edge for edge, site in assignment.items()}
        diagnostics.update({
            "arrivals": {prepared.node_ids[i]: arrival_arr[i] for i in range(n_nodes)},
            "remaining_to_sink": {prepared.node_ids[i]: remaining_arr[i] for i in range(n_nodes)},
            "edge_slack": slack,
            "site_contention": {
                site: {
                    "capacity": 1,
                    "eligible_edges": sorted(edge.id for edge in instance.cross_edges if site in edge.eligible_sites),
                    "assigned_edge": occupant.get(site),
                }
                for site in sorted(instance.sites)
            },
        })

    return Evaluation(
        feasible=True, objectives=objectives, diagnostics=diagnostics,
        lower_bound=lower_bound, evidence=evidence,
    )


def evaluate(instance_mapping: Mapping[str, Any], solution_mapping: Mapping[str, Any]) -> Evaluation:
    """Raise instance errors; return infeasible Evaluation for any invalid solution."""
    return evaluate_prepared(prepare_verifier(instance_mapping), solution_mapping, include_edge_details=True)
