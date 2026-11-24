"""Trusted weighted vertex cover discovery admission, bounds and feedback."""
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from random import Random
from typing import Any

from .evaluator import evaluate, evaluate_prepared, prepare_verifier
from .generator import generate_instance
from .model import SCHEMA_VERSION, TASK_ID, parse_instance


class WeightedVertexCoverDiscoveryTask:
    task_id = TASK_ID

    def prepare(self, raw):
        instance = parse_instance(raw)
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": instance.instance_id,
            "data": {
                "vertices": list(instance.vertex_ids),
                "weights": dict(instance.weights),
                "edges": [[u, v] for u, v in instance.edges],
            },
        }

    def objective_domain(self, raw):
        instance = parse_instance(raw)
        return (sum(instance.weights.values()),), (1,)

    def prepare_verifier(self, instance):
        return prepare_verifier(instance)

    def verify_prepared(self, prepared, solution, *, parent_solution=None):
        del parent_solution
        return evaluate_prepared(prepared, solution)

    def verify(self, instance, solution):
        return evaluate(instance, solution)

    def paradigm_catalog(self):
        return (
            {
                "id": "nemhauser_trotter_kernel_bnb",
                "regime": "exact_branch_and_reduce",
                "title": "Nemhauser-Trotter Half-Integral Kernelization + Branch-and-Reduce",
                "mechanism": "Solve the bipartite 2x vertex-cover LP relaxation via Hopcroft-Karp / min-cut to fix 0/1 Nemhauser-Trotter kernel vertices, apply degree-1/degree-2 folding, and branch on remaining core vertices.",
                "anti_pattern": "Do not tweak greedy weight/degree scoring heuristics or 1-for-k local swaps alone.",
            },
            {
                "id": "local_ratio_dual_primal",
                "regime": "spectral_relaxation_rounding",
                "title": "Bar-Yehuda-Even Local-Ratio Dual Packing + Reverse-Delete Pruning",
                "mechanism": "Grow dual edge/odd-cycle weights iteratively until vertices become tight, push tight vertices in stack order, then run reverse-delete redundancy elimination.",
                "anti_pattern": "Do not evaluate vertex greediness purely without dual residual weight tracking.",
            },
            {
                "id": "lns_cluster_destroy_repair",
                "regime": "metaheuristic_population",
                "title": "Connected-Component Destroy-and-Repair (Tabu / LNS)",
                "mechanism": "Destroy local high-degree neighborhoods (2-hop clusters) of an incumbent cover and solve the small induced subproblem via exact branch-and-bound.",
                "anti_pattern": "Do not restrict local search to dropping single vertices.",
            },
        )

    def certificate(self, instance, solution, result):
        cert = result.diagnostics.get("optimality_certificate") if isinstance(result.diagnostics, dict) else None
        if not result.feasible or not isinstance(cert, dict) or cert.get("status") != "verified":
            return None
        return {
            "schema_version": 1,
            "kind": f"wvc_{result.evidence.value}_certificate",
            "instance": instance,
            "solution": solution,
            "verification": asdict(result),
        }

    def reduce_instance(self, instance, evaluation, *, max_size=12):
        """Extract a valid induced subgraph around uncovered, redundant, or costly vertices."""
        inst = parse_instance(instance)
        if len(inst.vertex_ids) <= 4 or len(inst.edges) <= 2:
            return None
        target_cap = max(4, min(int(max_size), len(inst.vertex_ids) - 1))
        diag = (evaluation.get("diagnostics") or {}) if isinstance(evaluation, dict) else {}

        seeds: list[str] = []
        for pair in diag.get("uncovered_edges") or ():
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                seeds.extend([str(pair[0]), str(pair[1])])
        for item in diag.get("expensive_choices") or ():
            if isinstance(item, dict) and item.get("id"):
                seeds.append(str(item["id"]))
            elif isinstance(item, str):
                seeds.append(item)
        for vid in diag.get("redundant_vertices") or ():
            if isinstance(vid, str):
                seeds.append(vid)
        for vid in sorted(inst.vertex_ids, key=lambda v: (-inst.weights[v], -len(inst.adjacency[v]), v)):
            seeds.append(vid)

        core: list[str] = []
        core_set: set[str] = set()
        for vid in seeds:
            if vid in inst.weights and vid not in core_set:
                core.append(vid)
                core_set.add(vid)
                if len(core) >= target_cap:
                    break
        for vid in list(core):
            if len(core) >= target_cap:
                break
            for nb in inst.adjacency.get(vid, ()):
                if nb not in core_set:
                    core.append(nb)
                    core_set.add(nb)
                    if len(core) >= target_cap:
                        break

        induced_edges = [[u, v] for u, v in inst.edges if u in core_set and v in core_set]
        if len(core) >= len(inst.vertex_ids) or len(induced_edges) < 2:
            return None
        raw_reduced = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__diag_core",
            "data": {
                "vertices": core,
                "weights": {vid: inst.weights[vid] for vid in core},
                "edges": induced_edges,
            },
        }
        try:
            parse_instance(raw_reduced)
        except ValueError:
            return None
        return self.prepare(raw_reduced)

    def permute_instance(self, instance: Mapping[str, Any], *, seed: int = 1) -> dict[str, Any]:
        """Return an isomorphic WVC instance with relabeled v0.. IDs, shuffled lists, and swapped edge endpoints."""
        inst = parse_instance(instance)
        rng = Random(seed)

        vids = list(inst.vertex_ids)
        rng.shuffle(vids)
        v_map = {old: f"v{i}" for i, old in enumerate(vids)}

        vertices = [v_map[old] for old in vids]
        rng.shuffle(vertices)
        weights = {v_map[old]: inst.weights[old] for old in inst.vertex_ids}
        edges: list[list[str]] = []
        for u, v in inst.edges:
            nu, nv = v_map[u], v_map[v]
            edges.append([nv, nu] if rng.randrange(2) else [nu, nv])
        rng.shuffle(edges)

        raw_perm = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__iso_{seed}",
            "data": {
                "vertices": vertices,
                "weights": weights,
                "edges": edges,
            },
        }
        parse_instance(raw_perm)
        return raw_perm

    def subset_elements(self, instance: Mapping[str, Any]) -> list[str]:
        """Return vertex IDs eligible for delta-debugging subgraph reduction."""
        inst = parse_instance(instance)
        return list(inst.vertex_ids)

    def rebuild_from_subset(self, instance: Mapping[str, Any], kept: Sequence[str]) -> dict[str, Any] | None:
        """Rebuild an induced subgraph from kept vertex IDs if it induces >= 2 edges."""
        inst = parse_instance(instance)
        kept_set = {str(v) for v in kept}
        core = [v for v in inst.vertex_ids if v in kept_set]
        induced_edges = [[u, v] for u, v in inst.edges if u in kept_set and v in kept_set]
        if not core or len(induced_edges) < 2:
            return None
        raw_reduced = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": f"{inst.instance_id}__ddmin_{len(core)}",
            "data": {
                "vertices": core,
                "weights": {vid: inst.weights[vid] for vid in core},
                "edges": induced_edges,
            },
        }
        try:
            parse_instance(raw_reduced)
        except ValueError:
            return None
        return self.prepare(raw_reduced)

    def generate_adversarial_instances(self, *, seed: int, count: int = 2) -> list[dict[str, Any]]:
        """Generate unseen small WVC instances (size 8-16) for active adversarial probing."""
        rng = Random(seed)
        results: list[dict[str, Any]] = []
        for idx in range(max(0, int(count))):
            size = 8 + rng.randrange(9)
            sub_seed = seed * 1009 + idx * 97 + 17
            raw = dict(generate_instance(seed=sub_seed, size=size))
            raw["instance_id"] = f"wvc-adv-s{seed}-{idx}-n{size}"
            results.append(self.prepare(raw))
        return results

    def feedback(self, result):
        d = result.diagnostics
        return {
            "feasible": result.feasible,
            "objectives": result.objectives,
            "violations": list(result.violations)[:4],
            "lower_bound": result.lower_bound,
            "selected_count": d.get("selected_count"),
            "bound_gap": d.get("bound_gap"),
            "redundant_vertices": d.get("redundant_vertices", [])[:5],
            "redundant_weight": d.get("redundant_weight"),
            "expensive_choices": d.get("expensive_choices", [])[:5],
            "uncovered_edges": d.get("uncovered_edges", [])[:5],
        }

    def brief(self):
        return """Implement a standalone standard-library Python function solve(instance, budget) returning a JSON object.
Task: weighted_vertex_cover (minimum-weight vertex cover on a simple undirected graph).
Input has schema_version=1, task_id="weighted_vertex_cover", instance_id, and
data={"vertices":[str,...], "weights":{vid:int>=0,...}, "edges":[[u,v],...]}.
Return {"schema_version":1,"task_id":"weighted_vertex_cover",
"instance_id":instance["instance_id"],"solution":{"selected_vertices":[unique vertex IDs]}}.
Every edge [u,v] must have u or v (or both) in selected_vertices. Minimize sum of weights.
The host independently verifies membership, uniqueness, coverage and exact total weight.
Candidate-reported scores are ignored. Invalid covers have zero search score.
budget contains wall_seconds and seed. Only Python's standard library is available. Do not print.
Improve the algorithm across unseen graph structures (hubs, skewed weights, dense clusters, bipartite traps);
do not hard-code training instance IDs. Feedback includes bound gap, redundant vertices and expensive choices.
"""
