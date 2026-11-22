"""Standalone standard-library discovery seed for weighted minimum vertex cover."""
from random import Random
from time import monotonic


def solve(instance, budget):
    deadline = monotonic() + float(budget["wall_seconds"])
    rng = Random(int(budget["seed"]))
    data = instance["data"]
    vertices = list(data["vertices"])
    weights = {vid: int(data["weights"][vid]) for vid in vertices}
    edges = [(u, v) for u, v in data["edges"]]
    adj = {vid: [] for vid in vertices}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)

    selected = set()
    uncovered = set(edges)
    while uncovered:
        deg = {}
        for u, v in uncovered:
            deg[u] = deg.get(u, 0) + 1
            deg[v] = deg.get(v, 0) + 1
        pick = min(deg, key=lambda vid: (weights[vid] / deg[vid], weights[vid], vid))
        selected.add(pick)
        uncovered = {e for e in uncovered if pick not in e}

    def prune(cover):
        for vid in sorted(cover, key=lambda v: (-weights[v], v)):
            if all(nb in cover for nb in adj[vid]):
                cover.remove(vid)

    prune(selected)
    best = set(selected)
    best_weight = sum(weights[v] for v in best)

    improved = True
    while improved and monotonic() < deadline:
        improved = False
        order = sorted(best, key=lambda v: (-weights[v], rng.random()))
        for vid in order:
            if monotonic() >= deadline:
                break
            needed = [nb for nb in adj[vid] if nb not in best]
            if sum(weights[nb] for nb in needed) < weights[vid]:
                cand = (best - {vid}) | set(needed)
                prune(cand)
                w = sum(weights[v] for v in cand)
                if w < best_weight:
                    best, best_weight, improved = cand, w, True
                    break

    return {
        "schema_version": 1,
        "task_id": "weighted_vertex_cover",
        "instance_id": instance["instance_id"],
        "solution": {"selected_vertices": sorted(best)},
    }
