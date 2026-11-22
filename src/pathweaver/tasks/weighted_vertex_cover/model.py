"""Strict weighted minimum vertex cover instance representation and validation."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pathweaver.core.contracts import require_nonneg_int, require_text, validate_instance_envelope

SCHEMA_VERSION = 1
TASK_ID = "weighted_vertex_cover"


@dataclass(frozen=True)
class Instance:
    instance_id: str
    vertex_ids: tuple[str, ...]
    weights: Mapping[str, int]
    edges: tuple[tuple[str, str], ...]
    adjacency: Mapping[str, tuple[str, ...]]


def parse_instance(raw: Any) -> Instance:
    instance_id, data = validate_instance_envelope(raw, task_id=TASK_ID, schema_version=SCHEMA_VERSION)

    raw_vertices = data.get("vertices")
    if not isinstance(raw_vertices, Sequence) or isinstance(raw_vertices, (str, bytes)) or not raw_vertices:
        raise ValueError("data.vertices must be a non-empty array of vertex IDs")
    raw_weights = data.get("weights")
    if not isinstance(raw_weights, Mapping):
        raise ValueError("data.weights must be an object mapping vertex IDs to nonnegative integer weights")

    vertex_ids: list[str] = []
    seen_vertices: set[str] = set()
    for index, item in enumerate(raw_vertices):
        vid = require_text(item, f"vertices[{index}]")
        if vid in seen_vertices:
            raise ValueError(f"duplicate vertex id {vid!r}")
        seen_vertices.add(vid)
        vertex_ids.append(vid)

    if set(raw_weights.keys()) != seen_vertices:
        missing = sorted(seen_vertices - set(raw_weights.keys()))
        extra = sorted(set(raw_weights.keys()) - seen_vertices, key=str)
        raise ValueError(f"data.weights keys must exactly match data.vertices (missing={missing}, extra={extra})")
    weights = {vid: require_nonneg_int(raw_weights[vid], f"weights[{vid!r}]") for vid in vertex_ids}

    raw_edges = data.get("edges")
    if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, (str, bytes)):
        raise ValueError("data.edges must be an array")
    seen_edges: set[tuple[str, str]] = set()
    edges: list[tuple[str, str]] = []
    adj: dict[str, list[str]] = {vid: [] for vid in vertex_ids}
    for index, pair in enumerate(raw_edges):
        if not isinstance(pair, Sequence) or isinstance(pair, (str, bytes)) or len(pair) != 2:
            raise ValueError(f"edges[{index}] must be a two-element array [u, v]")
        u = require_text(pair[0], f"edges[{index}][0]")
        v = require_text(pair[1], f"edges[{index}][1]")
        if u not in weights or v not in weights:
            raise ValueError(f"edges[{index}] references unknown vertex ({u!r}, {v!r})")
        if u == v:
            raise ValueError(f"edges[{index}] cannot be a self-loop on {u!r}")
        canonical = (u, v) if u < v else (v, u)
        if canonical in seen_edges:
            raise ValueError(f"duplicate undirected edge {canonical!r}")
        seen_edges.add(canonical)
        edges.append(canonical)
        adj[canonical[0]].append(canonical[1])
        adj[canonical[1]].append(canonical[0])

    return Instance(
        instance_id=instance_id,
        vertex_ids=tuple(vertex_ids),
        weights=weights,
        edges=tuple(edges),
        adjacency={vid: tuple(sorted(neighbors)) for vid, neighbors in adj.items()},
    )
