"""EDA-only discovery admission, objective bounds and compact trusted feedback."""
from dataclasses import asdict
from functools import reduce
from math import gcd

from .evaluator import _arrival_times, evaluate, evaluate_prepared, prepare_verifier
from .model import TASK_ID, InvalidInstanceError, find_matching, geometric_length, parse_instance


class EdaDiscoveryTask:
    task_id = TASK_ID

    def prepare(self, raw):
        parse_instance(raw)
        return {key: raw[key] for key in ("schema_version", "task_id", "instance_id", "data")}

    def objective_domain(self, raw):
        instance = parse_instance(raw)
        upper_delays = {}
        length_bound = 0
        delay_unit, length_unit = 0, 0
        for edge in instance.edges:
            if edge.delay is not None:
                values = [edge.delay]
            else:
                lengths = [geometric_length(instance, edge, site) for site in edge.eligible_sites]
                length_bound += max(lengths)
                length_unit = reduce(gcd, lengths, length_unit)
                values = [edge.base_delay + edge.alpha * length for length in lengths]
            upper_delays[edge.id] = max(values)
            delay_unit = reduce(gcd, values, delay_unit)
        arrivals, _ = _arrival_times(instance, upper_delays)
        return (max(arrivals.values()), length_bound), (delay_unit or 1, length_unit or 1)

    def prepare_verifier(self, instance):
        return prepare_verifier(instance)

    def verify_prepared(self, prepared, solution, *, parent_solution=None):
        del parent_solution
        return evaluate_prepared(prepared, solution, include_edge_details=False)

    def verify(self, instance, solution):
        return evaluate(instance, solution)

    def paradigm_catalog(self):
        return (
            {
                "id": "lagrangian_subgradient_matching",
                "regime": "spectral_relaxation_rounding",
                "title": "Lagrangian Path-Dual Subgradient Matching",
                "mechanism": "Maintain dual multipliers on critical/near-critical DAG paths via subgradient ascent across rounds, solving global min-cost bipartite matching under composite (alpha*length + lambda_path) costs.",
                "anti_pattern": "Do not bump scalar edge weights greedily for a single round's critical path without dual convergence.",
            },
            {
                "id": "beam_conflict_branching",
                "regime": "exact_branch_and_reduce",
                "title": "Critical-Conflict Beam / Branch-and-Bound Search",
                "mechanism": "Identify Hall-contested bottleneck sites and coupled multi-edge paths, branching explicitly on conflicting site assignments while pruning via relaxed DAG lower bounds.",
                "anti_pattern": "Do not rely on sequential 2-swap local search when bottleneck sites are saturated.",
            },
            {
                "id": "bipartite_hall_bottleneck_matching",
                "regime": "bipartite_matching_flow",
                "title": "Bottleneck-Threshold Bipartite Matching + Feasible Potentials",
                "mechanism": "Binary search the minimum feasible DAG threshold T_hall admitting a complete matching under relaxed arrival+remaining caps, then re-optimize L via vertex potentials.",
                "anti_pattern": "Do not evaluate only at T_relaxed_lb or unguided minimum length.",
            },
        )

    def feedback(self, result):
        diagnostics = result.diagnostics
        path = diagnostics.get("critical_path", [])
        edges = diagnostics.get("edges", {})
        return {"feasible": result.feasible, "objectives": result.objectives,
                "violations": list(result.violations)[:12], "lower_bound": result.lower_bound,
                "evidence": result.evidence,
                "optimality_certificate": diagnostics.get("optimality_certificate"),
                "critical_path_count": len(path), "critical_path": path[:16],
                "critical_edges": {edge: edges[edge] for edge in path[:12] if edge in edges}}

    def certificate(self, instance, solution, result):
        if not result.feasible or result.diagnostics.get("optimality_certificate", {}).get("status") != "verified":
            return None
        return {"schema_version": 1, "kind": f"eda_{result.evidence.value}_certificate",
                "instance": instance, "solution": solution, "verification": asdict(result)}

    def reduce_instance(self, instance, evaluation, *, max_size=12):
        """Extract a smaller valid Hall/critical-path sub-instance reproducing the bottleneck."""
        inst = parse_instance(instance)
        if len(inst.edges) <= 2:
            return None
        diag = (evaluation.get("diagnostics") or {}) if isinstance(evaluation, dict) else {}
        crit_path = [str(eid) for eid in (diag.get("critical_path") or [])]
        edge_by_id = {edge.id: edge for edge in inst.edges}

        kept_ids: list[str] = [eid for eid in crit_path if eid in edge_by_id]
        if not kept_ids:
            kept_ids = [edge.id for edge in inst.cross_edges[:max(1, min(3, max_size))]]
        kept_set = set(kept_ids)

        movable_count = sum(1 for eid in kept_set if edge_by_id[eid].delay is None)
        crit_sites = {
            site for eid in kept_set if edge_by_id[eid].delay is None
            for site in edge_by_id[eid].eligible_sites
        }
        for edge in inst.cross_edges:
            if movable_count >= max_size:
                break
            if edge.id not in kept_set and (not crit_sites or any(s in crit_sites for s in edge.eligible_sites)):
                kept_ids.append(edge.id)
                kept_set.add(edge.id)
                movable_count += 1
        if movable_count == 0:
            for edge in inst.cross_edges[:max_size]:
                if edge.id not in kept_set:
                    kept_ids.append(edge.id)
                    kept_set.add(edge.id)
                    movable_count += 1

        if not kept_set or len(kept_set) >= len(inst.edges):
            return None

        kept_edges = [edge for edge in inst.edges if edge.id in kept_set]
        node_ids = {edge.source for edge in kept_edges} | {edge.target for edge in kept_edges}
        site_ids = {site for edge in kept_edges if edge.delay is None for site in edge.eligible_sites}
        raw_reduced = {
            "schema_version": 1,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__diag_reduced",
            "data": {
                "nodes": [
                    {"id": n.id, "x": n.x, "y": n.y, "tier": n.tier}
                    for n in inst.nodes.values() if n.id in node_ids
                ],
                "sites": [
                    {"id": s.id, "x": s.x, "y": s.y}
                    for s in inst.sites.values() if s.id in site_ids
                ],
                "edges": [
                    (
                        {"id": e.id, "source": e.source, "target": e.target, "delay": e.delay}
                        if e.delay is not None
                        else {
                            "id": e.id, "source": e.source, "target": e.target,
                            "base_delay": e.base_delay, "alpha": e.alpha,
                            "eligible_sites": list(e.eligible_sites),
                        }
                    )
                    for e in kept_edges
                ],
            },
        }
        try:
            parsed = parse_instance(raw_reduced)
        except InvalidInstanceError:
            return None
        if find_matching(parsed) is None:
            return None
        return self.prepare(raw_reduced)

    def brief(self):
        return '''Implement a standalone Python standard-library function solve(instance, budget) returning a JSON object.
instance has schema_version=1, task_id="eda_assignment", instance_id, and data with nodes, sites, edges.
Nodes: {id,x,y,tier}; sites: {id,x,y}. Edges have {id,source,target} and either fixed nonnegative delay,
or {base_delay,alpha,eligible_sites} for cross-tier edges. Give every cross-tier edge exactly one eligible
site; every site has global capacity one. Length is Manhattan(source,site)+Manhattan(site,target), ignoring tier.
Cross-edge delay = base_delay + alpha*length. Fixed edges keep delay. The graph is a DAG.
T is the longest path over the COMPLETE DAG (including disconnected fixed paths); L is the sum of ALL cross-edge lengths.
Return {"schema_version":1,"task_id":"eda_assignment","instance_id":instance["instance_id"],
        "solution":{"assignment":{edge_id:site_id}}}. Candidate-reported scores are ignored.
budget is a dict with wall_seconds and seed. No pathweaver or third-party modules are installed in the sandbox.
Use the input instance, not instance IDs or memorized assignments. Do not print; return the solution.
Improve algorithm structure while preserving constraints. Verification and scoring run outside your process.
'''
