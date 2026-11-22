"""Seeded synthetic instance generator for weighted minimum vertex cover."""
from random import Random
from typing import Any

from .model import SCHEMA_VERSION, TASK_ID


def generate_instance(*, seed: int, size: int) -> dict[str, Any]:
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(size) is not int or size < 2:
        raise ValueError("size must be an integer >= 2")
    rng = Random(seed)
    vertices = [f"v{i}" for i in range(size)]
    weights: dict[str, int] = {}
    for i, vid in enumerate(vertices):
        weights[vid] = rng.randint(15, 45) if i % 4 == 0 else rng.randint(2, 18)

    edge_prob = min(0.65, max(0.18, 3.2 / size + 0.14))
    edges: set[tuple[int, int]] = set()
    for i in range(1, size):
        parent = rng.randrange(0, i)
        edges.add((parent, i))
    for i in range(size):
        for j in range(i + 1, size):
            if rng.random() < edge_prob:
                edges.add((i, j))

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": f"wvc-s{seed}-n{size}",
        "data": {
            "vertices": vertices,
            "weights": weights,
            "edges": [[f"v{u}", f"v{v}"] for u, v in sorted(edges)],
        },
    }
