"""Small reproducible DAGs with planted capacity-one feasible assignments."""

from random import Random
from typing import Any, Mapping

from .model import SCHEMA_VERSION, TASK_ID


def generate(*, seed: int, size: int) -> Mapping[str, Any]:
    """Generate ``size`` cross-tier edges; every instance has a full matching.

    Cross-tier stages form a chain joined by fixed same-tier edges. Fixed
    two-stage shortcuts add competing paths for sizes greater than one. Each
    cross-tier edge can use its own planted site, a shared spare site, and a
    small selection of other sites. A local RNG controls every random choice.
    """
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(size) is not int or size < 1:
        raise ValueError("size must be a positive integer (number of cross-tier edges)")
    rng = Random(seed)
    coordinate_limit = max(12, 3 * size)
    nodes = [
        {
            "id": f"n{index}",
            "x": rng.randint(0, coordinate_limit),
            "y": rng.randint(0, coordinate_limit),
            "tier": ((index + 1) // 2) % 2,
        }
        for index in range(2 * size)
    ]
    spare_count = max(1, size // 3)
    sites = [
        {
            "id": f"s{index}",
            "x": rng.randint(0, coordinate_limit),
            "y": rng.randint(0, coordinate_limit),
        }
        for index in range(size + spare_count)
    ]
    site_ids = [site["id"] for site in sites]
    edges: list[dict[str, Any]] = []
    for index in range(size):
        eligible = {
            f"s{index}",
            f"s{(index + 1) % size}",
            f"s{size + index % spare_count}",
            *rng.sample(site_ids, min(3, len(site_ids))),
        }
        edges.append(
            {
                "id": f"cross{index}",
                "source": f"n{2 * index}",
                "target": f"n{2 * index + 1}",
                "base_delay": rng.randint(0, 8),
                "alpha": rng.randint(1, 3),
                "eligible_sites": sorted(eligible),
            }
        )
        if index + 1 < size:
            edges.append(
                {
                    "id": f"fixed{index}",
                    "source": f"n{2 * index + 1}",
                    "target": f"n{2 * index + 2}",
                    "delay": rng.randint(0, 12),
                }
            )
            edges.append(
                {
                    "id": f"shortcut{index}",
                    "source": f"n{2 * index}",
                    "target": f"n{2 * index + 3}",
                    "delay": rng.randint(2 * coordinate_limit, 12 * coordinate_limit),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": f"eda_assignment_generated_{seed}_{size}",
        "data": {"nodes": nodes, "sites": sites, "edges": edges},
        "provenance": {
            "kind": "generated",
            "generator": "eda_assignment_seeded_v1",
            "seed": seed,
            "size": size,
        },
    }
