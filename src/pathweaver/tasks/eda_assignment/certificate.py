"""Check assignment duality witnesses using only the trusted task representation.

This module imports neither the solver nor its Hungarian implementation. The
evaluator supplies independently recomputed objectives and relaxed DAG paths.
All certificate fields are untrusted; no claimed score, cap, matrix or assignment
from the certificate is used in place of the mathematical instance.
"""
from collections.abc import Mapping

from .model import geometric_length


METHOD = "relaxed_path_matching_duality"


def _potentials(raw, identifiers, name):
    if not isinstance(raw, Mapping) or set(raw) != set(identifiers):
        raise ValueError(f"{name} must contain exactly the reconstructed IDs")
    if any(type(value) is not int for value in raw.values()):
        raise ValueError(f"{name} must contain integer potentials, excluding bools")
    return raw


def check_certificate(instance, assignment, certificate, *, objectives, lower_bound,
                      relaxed_arrivals, relaxed_remaining):
    """Return verified/rejected/absent diagnostics, without changing feasibility.

For every T=T_lb solution, each variable edge must satisfy its relaxed-path cap.
The reconstructed capacity matching is a necessary relaxation of those solutions.
An exact dual witness proves minimum L over that relaxation; independently
attaining T_lb therefore proves lexicographic optimality of this finite solution.
"""
    if certificate is None:
        return {"status": "absent"}
    try:
        fields = {"schema_version", "method", "T_lower_bound", "row_potentials", "site_potentials"}
        if not isinstance(certificate, Mapping) or set(certificate) != fields:
            raise ValueError("Unexpected optimality certificate fields")
        if type(certificate["schema_version"]) is not int or certificate["schema_version"] != 1:
            raise ValueError("Unsupported optimality certificate schema")
        if certificate["method"] != METHOD:
            raise ValueError("Unknown optimality certificate method")
        bound = certificate["T_lower_bound"]
        if type(bound) is not int or bound != lower_bound[0] or objectives[0] != bound:
            raise ValueError("The complete DAG must independently attain the claimed T lower bound")

        forced = {edge.id: edge.eligible_sites[0] for edge in instance.cross_edges
                  if len(edge.eligible_sites) == 1}
        reserved = set(forced.values())
        movable = [edge for edge in instance.cross_edges if edge.id not in forced]
        sites = {site for edge in movable for site in edge.eligible_sites if site not in reserved}
        rows = _potentials(certificate["row_potentials"], (edge.id for edge in movable), "row_potentials")
        columns = _potentials(certificate["site_potentials"], sites, "site_potentials")
        if any(value > 0 for value in columns.values()):
            raise ValueError("Capacity-at-most-one column potentials must be nonpositive")

        primal = 0
        for edge in movable:
            assigned = assignment[edge.id]  # Feasibility was independently checked first.
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
        return {"status": "verified", "method": METHOD, "T_lower_bound": bound,
                "matching_primal": primal, "matching_dual": dual,
                "forced_length": fixed_length, "certified_objectives": objectives}
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "rejected", "reason": str(error)}
