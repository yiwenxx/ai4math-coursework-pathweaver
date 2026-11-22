"""Check assignment duality and Hall-bottleneck witnesses using only trusted task data.

This module imports neither the solver nor its Hungarian implementation. The
evaluator supplies independently recomputed objectives and relaxed DAG paths.
Supports:
1. ``relaxed_path_matching_duality``: proves finite optimality when T = T_relaxed_lb.
2. ``hall_bottleneck_and_dual``: proves T* >= T_hall > T_relaxed_lb via a Hall
   conflict witness at T_hall - 1, plus Hungarian dual optimality at T_hall
   (certifying FINITE_OPTIMAL even on capacity-coupled T* > T_lb instances, or
   CERTIFIED_BOUND when a verified tighter lower bound T_hall is established).
3. ``hall_bottleneck_lower_bound``: standalone Hall conflict lower bound tightening.
"""
from collections.abc import Mapping

from .model import geometric_length


METHOD = "relaxed_path_matching_duality"
HALL_DUAL_METHOD = "hall_bottleneck_and_dual"
HALL_BOUND_METHOD = "hall_bottleneck_lower_bound"


def _potentials(raw, identifiers, name):
    if not isinstance(raw, Mapping) or set(raw) != set(identifiers):
        raise ValueError(f"{name} must contain exactly the reconstructed IDs")
    if any(type(value) is not int for value in raw.values()):
        raise ValueError(f"{name} must contain integer potentials, excluding bools")
    return raw


def _verify_hall_conflict(instance, blocking_ids, threshold, relaxed_arrivals, relaxed_remaining, reserved, movable_by_id):
    """Independently verify |N_{<=threshold}(A)| < |A| for a Hall blocking set A."""
    if not isinstance(blocking_ids, list) or not blocking_ids:
        raise ValueError("hall_blocking_set must be a nonempty list of edge IDs")
    if len(set(blocking_ids)) != len(blocking_ids):
        raise ValueError("hall_blocking_set must not contain duplicate edge IDs")

    # Also allow singleton forced edge conflict if a forced edge exceeds threshold alone.
    if len(blocking_ids) == 1 and blocking_ids[0] not in movable_by_id:
        forced_map = {e.id: e for e in instance.cross_edges if len(e.eligible_sites) == 1}
        edge = forced_map.get(blocking_ids[0])
        if edge is None:
            raise ValueError(f"Unknown edge in hall_blocking_set: {blocking_ids[0]!r}")
        length = geometric_length(instance, edge, edge.eligible_sites[0])
        min_through = relaxed_arrivals[edge.source] + edge.base_delay + edge.alpha * length + relaxed_remaining[edge.target]
        if min_through <= threshold:
            raise ValueError("Singleton forced edge does not violate threshold")
        return 0

    neighborhood: set[str] = set()
    for eid in blocking_ids:
        edge = movable_by_id.get(eid)
        if edge is None:
            raise ValueError(f"hall_blocking_set references non-movable/unknown edge {eid!r}")
        cap = threshold - relaxed_arrivals[edge.source] - relaxed_remaining[edge.target]
        for site in edge.eligible_sites:
            if site in reserved:
                continue
            length = geometric_length(instance, edge, site)
            if edge.base_delay + edge.alpha * length <= cap:
                neighborhood.add(site)
    if len(neighborhood) >= len(blocking_ids):
        raise ValueError(
            f"Hall condition failed at T<={threshold}: |N(A)|={len(neighborhood)} >= |A|={len(blocking_ids)}"
        )
    return len(neighborhood)


def _verify_matching_duals(instance, assignment, rows_raw, cols_raw, bound,
                           relaxed_arrivals, relaxed_remaining, forced, reserved, movable, sites, objectives):
    rows = _potentials(rows_raw, (edge.id for edge in movable), "row_potentials")
    columns = _potentials(cols_raw, sites, "site_potentials")
    if any(value > 0 for value in columns.values()):
        raise ValueError("Capacity-at-most-one column potentials must be nonpositive")

    primal = 0
    for edge in movable:
        assigned = assignment[edge.id]
        if assigned not in sites:
            raise ValueError("Matching uses a globally reserved singleton site")
        cap = bound - relaxed_arrivals[edge.source] - relaxed_remaining[edge.target]
        assigned_allowed = False
        for site in edge.eligible_sites:
            if site in reserved:
                continue
            length = geometric_length(instance, edge, site)
            if edge.base_delay + edge.alpha * length > cap:
                continue
            reduced = length - rows[edge.id] - columns[site]
            if reduced < 0:
                raise ValueError(f"Negative reduced cost for edge {edge.id!r}, site {site!r}")
            if site == assigned:
                assigned_allowed = True
                if reduced != 0:
                    raise ValueError("Assigned edges must have zero reduced cost")
                primal += length
        if not assigned_allowed:
            raise ValueError("Assigned edge violates the independently reconstructed path cap")

    used = {assignment[edge.id] for edge in movable}
    if any(columns[site] != 0 for site in sites - used):
        raise ValueError("Unused sites must have zero dual potential")
    dual = sum(rows.values()) + sum(columns.values())
    if primal != dual:
        raise ValueError("Matching primal and dual costs differ")
    fixed_length = sum(geometric_length(instance, edge, forced[edge.id])
                       for edge in instance.cross_edges if edge.id in forced)
    if primal + fixed_length != objectives[1]:
        raise ValueError("Certified matching cost does not reproduce the independent L")
    return primal, dual, fixed_length


def check_certificate(instance, assignment, certificate, *, objectives, lower_bound,
                      relaxed_arrivals, relaxed_remaining):
    """Return verified/rejected/absent diagnostics, without changing feasibility."""
    if certificate is None:
        return {"status": "absent"}
    try:
        if not isinstance(certificate, Mapping):
            raise ValueError("Optimality certificate must be a mapping")
        if type(certificate.get("schema_version")) is not int or certificate["schema_version"] != 1:
            raise ValueError("Unsupported optimality certificate schema")
        method = certificate.get("method")

        forced = {edge.id: edge.eligible_sites[0] for edge in instance.cross_edges
                  if len(edge.eligible_sites) == 1}
        reserved = set(forced.values())
        movable = [edge for edge in instance.cross_edges if edge.id not in forced]
        movable_by_id = {edge.id: edge for edge in movable}
        sites = {site for edge in movable for site in edge.eligible_sites if site not in reserved}

        if method == METHOD:
            fields = {"schema_version", "method", "T_lower_bound", "row_potentials", "site_potentials"}
            if set(certificate) != fields:
                raise ValueError("Unexpected optimality certificate fields")
            bound = certificate["T_lower_bound"]
            if type(bound) is not int or bound != lower_bound[0] or objectives[0] != bound:
                raise ValueError("The complete DAG must independently attain the claimed T lower bound")
            primal, dual, fixed_length = _verify_matching_duals(
                instance, assignment, certificate["row_potentials"], certificate["site_potentials"],
                bound, relaxed_arrivals, relaxed_remaining, forced, reserved, movable, sites, objectives,
            )
            return {
                "status": "verified", "method": METHOD, "evidence": "finite_optimal",
                "T_lower_bound": bound, "matching_primal": primal, "matching_dual": dual,
                "forced_length": fixed_length, "certified_objectives": list(objectives),
            }

        if method == HALL_BOUND_METHOD:
            fields = {"schema_version", "method", "T_lower_bound", "hall_blocking_set"}
            if set(certificate) != fields:
                raise ValueError("Unexpected Hall lower-bound certificate fields")
            bound = certificate["T_lower_bound"]
            if type(bound) is not int or bound <= lower_bound[0]:
                raise ValueError("Hall bound must strictly improve the capacity-relaxed T lower bound")
            n_size = _verify_hall_conflict(
                instance, certificate["hall_blocking_set"], bound - 1,
                relaxed_arrivals, relaxed_remaining, reserved, movable_by_id,
            )
            return {
                "status": "verified", "method": HALL_BOUND_METHOD, "evidence": "certified_bound",
                "T_lower_bound": bound, "blocking_set_size": len(certificate["hall_blocking_set"]),
                "neighborhood_size": n_size, "certified_gap_T": max(0, objectives[0] - bound),
            }

        if method == HALL_DUAL_METHOD:
            fields = {"schema_version", "method", "T_lower_bound", "hall_blocking_set", "row_potentials", "site_potentials"}
            if set(certificate) != fields:
                raise ValueError("Unexpected Hall+dual certificate fields")
            bound = certificate["T_lower_bound"]
            if type(bound) is not int or bound <= lower_bound[0]:
                raise ValueError("Hall+dual T_lower_bound must strictly exceed capacity-relaxed lower bound")
            n_size = _verify_hall_conflict(
                instance, certificate["hall_blocking_set"], bound - 1,
                relaxed_arrivals, relaxed_remaining, reserved, movable_by_id,
            )
            if objectives[0] != bound:
                raise ValueError("Complete DAG T does not match certified Hall bottleneck lower bound")
            primal, dual, fixed_length = _verify_matching_duals(
                instance, assignment, certificate["row_potentials"], certificate["site_potentials"],
                bound, relaxed_arrivals, relaxed_remaining, forced, reserved, movable, sites, objectives,
            )
            return {
                "status": "verified", "method": HALL_DUAL_METHOD, "evidence": "finite_optimal",
                "T_lower_bound": bound, "blocking_set_size": len(certificate["hall_blocking_set"]),
                "neighborhood_size": n_size, "matching_primal": primal, "matching_dual": dual,
                "forced_length": fixed_length, "certified_objectives": list(objectives),
            }

        raise ValueError(f"Unknown optimality certificate method: {method!r}")
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "rejected", "reason": str(error)}
