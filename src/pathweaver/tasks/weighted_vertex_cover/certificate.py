"""Solver-independent NP-hard certificates for Weighted Minimum Vertex Cover.

Supports:
1. ``valid_inequality_dual``: Scaled integer dual packing over edges, odd cycles,
   and cliques, certifying tightened lower bounds (``certified_bound``) or exact
   optimality (``finite_optimal``) even when integral edge packing has a gap.
2. ``bnb_proof_tree``: Exhaustive Branch-and-Bound proof tree verified via the
   domain-neutral ``verify_bnb_proof_tree`` kernel (``finite_optimal``).
"""
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pathweaver.core.certificates import verify_bnb_proof_tree
from pathweaver.core.contracts import EvidenceLevel
from .model import Instance


VALID_INEQUALITY_METHOD = "valid_inequality_dual"
BNB_TREE_METHOD = "bnb_proof_tree"


@dataclass(frozen=True)
class _WvcBranchState:
    included: frozenset[str]
    excluded: frozenset[str]
    conflict: bool = False


def _residual_edge_packing_lb(instance: Instance, state: _WvcBranchState) -> int:
    """Sound integer edge-packing lower bound on residual uncovered edges + fixed weight."""
    fixed_weight = sum(instance.weights[v] for v in state.included)
    residual = {
        v: instance.weights[v]
        for v in instance.vertex_ids
        if v not in state.included and v not in state.excluded
    }
    dual = 0
    for u, v in instance.edges:
        if u in state.included or v in state.included:
            continue
        if u in state.excluded and v in state.excluded:
            return fixed_weight  # Infeasible state; handled by is_infeasible_fn too.
        ru = residual.get(u, 0)
        rv = residual.get(v, 0)
        slack = min(ru, rv)
        if slack > 0:
            residual[u] -= slack
            residual[v] -= slack
            dual += slack
    return fixed_weight + dual


def _check_valid_inequality_dual(
    instance: Instance,
    cert: Mapping[str, Any],
    *,
    total_weight: int,
    base_lower_bound: int,
) -> dict[str, Any]:
    allowed = {"schema_version", "method", "scale", "edges", "odd_cycles", "cliques"}
    if not set(cert).issubset(allowed) or "scale" not in cert:
        raise ValueError("Invalid valid_inequality_dual fields")
    scale = cert["scale"]
    if type(scale) is not int or scale < 1:
        raise ValueError("Dual scale must be a positive integer")

    edge_set = set(instance.edges)
    adj = {v: set(nbs) for v, nbs in instance.adjacency.items()}
    vertex_loads: dict[str, int] = defaultdict(int)
    scaled_dual_sum = 0

    for item in cert.get("edges", ()):
        if not isinstance(item, list) or len(item) != 3:
            raise ValueError("Edge dual entries must be [u, v, weight]")
        u, v, y = item
        if type(y) is not int or y < 0:
            raise ValueError("Dual multipliers must be nonnegative integers")
        pair = (u, v) if str(u) <= str(v) else (v, u)
        if pair not in edge_set:
            raise ValueError(f"Edge dual references nonexistent edge {item[:2]!r}")
        vertex_loads[u] += y
        vertex_loads[v] += y
        scaled_dual_sum += y  # rhs = 1

    for item in cert.get("odd_cycles", ()):
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Odd-cycle dual entries must be [[v1,...,v_{2k+1}], weight]")
        verts, y = item
        if type(y) is not int or y < 0:
            raise ValueError("Dual multipliers must be nonnegative integers")
        if not isinstance(verts, list) or len(verts) < 3 or len(verts) % 2 == 0 or len(set(verts)) != len(verts):
            raise ValueError("Odd-cycle dual requires an odd simple cycle of length >= 3")
        for idx, u in enumerate(verts):
            w = verts[(idx + 1) % len(verts)]
            if u not in adj or w not in adj[u]:
                raise ValueError(f"Declared odd cycle missing graph edge ({u!r}, {w!r})")
            vertex_loads[u] += y
        rhs = (len(verts) + 1) // 2
        scaled_dual_sum += y * rhs

    for item in cert.get("cliques", ()):
        if not isinstance(item, list) or len(item) != 2:
            raise ValueError("Clique dual entries must be [[v1,...,vr], weight]")
        verts, y = item
        if type(y) is not int or y < 0:
            raise ValueError("Dual multipliers must be nonnegative integers")
        if not isinstance(verts, list) or len(verts) < 3 or len(set(verts)) != len(verts):
            raise ValueError("Clique dual requires >= 3 distinct vertices")
        for i in range(len(verts)):
            u = verts[i]
            if u not in adj:
                raise ValueError(f"Unknown vertex in clique: {u!r}")
            for j in range(i + 1, len(verts)):
                if verts[j] not in adj[u]:
                    raise ValueError(f"Declared clique missing graph edge ({u!r}, {verts[j]!r})")
            vertex_loads[u] += y
        rhs = len(verts) - 1
        scaled_dual_sum += y * rhs

    for vid, load in vertex_loads.items():
        if load > scale * instance.weights[vid]:
            raise ValueError(f"Dual load {load} exceeds scaled capacity {scale * instance.weights[vid]} at {vid!r}")

    certified_lb = (scaled_dual_sum + scale - 1) // scale
    if certified_lb > total_weight:
        raise ValueError(f"Soundness error: dual bound {certified_lb} exceeds feasible weight {total_weight}")

    if certified_lb == total_weight:
        evidence = EvidenceLevel.FINITE_OPTIMAL.value
    elif certified_lb > base_lower_bound:
        evidence = EvidenceLevel.CERTIFIED_BOUND.value
    else:
        evidence = EvidenceLevel.EXPERIMENTAL.value
    return {
        "status": "verified",
        "method": VALID_INEQUALITY_METHOD,
        "evidence": evidence,
        "certified_lower_bound": certified_lb,
        "base_lower_bound": base_lower_bound,
        "certified_gap": total_weight - certified_lb,
    }


def _check_bnb_tree(
    instance: Instance,
    cert: Mapping[str, Any],
    *,
    total_weight: int,
) -> dict[str, Any]:
    tree = cert.get("tree")
    if tree is None:
        raise ValueError("bnb_proof_tree certificate requires a `tree` field")
    adj = instance.adjacency
    weights = instance.weights

    def apply_branch(state: _WvcBranchState, var: Any, choice: int) -> _WvcBranchState:
        if state.conflict or not isinstance(var, str) or var not in weights:
            raise ValueError(f"Invalid branch vertex: {var!r}")
        if var in state.included or var in state.excluded:
            raise ValueError(f"Duplicate branch on already-decided vertex {var!r}")
        if choice == 1:
            return _WvcBranchState(state.included | {var}, state.excluded, False)
        # Excluding var forces all its neighbors into the vertex cover.
        forced = set(adj[var])
        if forced & state.excluded:
            return _WvcBranchState(state.included, state.excluded | {var}, True)
        return _WvcBranchState(state.included | forced, state.excluded | {var}, False)

    def is_infeasible(state: _WvcBranchState) -> bool:
        if state.conflict:
            return True
        return any(u in state.excluded and v in state.excluded for u, v in instance.edges)

    def evaluate_leaf(state: _WvcBranchState, node: Mapping[str, Any]) -> int:
        if state.conflict:
            raise ValueError("Incumbent leaf reached from infeasible branch state")
        verts = node.get("selected_vertices")
        if not isinstance(verts, list) or len(set(verts)) != len(verts):
            raise ValueError("Incumbent leaf must supply unique selected_vertices")
        sel = set(verts)
        if not state.included.issubset(sel) or (sel & state.excluded):
            raise ValueError("Incumbent leaf violates fixed branch assignments")
        if any(u not in sel and v not in sel for u, v in instance.edges):
            raise ValueError("Incumbent leaf is not a valid vertex cover")
        return sum(weights[v] for v in sel)

    outcome = verify_bnb_proof_tree(
        tree,
        root_state=_WvcBranchState(frozenset(), frozenset(), False),
        apply_branch=apply_branch,
        lower_bound_fn=lambda st: _residual_edge_packing_lb(instance, st),
        is_infeasible_fn=is_infeasible,
        evaluate_leaf_fn=evaluate_leaf,
        incumbent_objective=total_weight,
    )
    if outcome.status != "verified":
        raise ValueError(outcome.reason or "BnB proof tree verification failed")
    return {
        "status": "verified",
        "method": BNB_TREE_METHOD,
        "evidence": EvidenceLevel.FINITE_OPTIMAL.value,
        "certified_lower_bound": total_weight,
        "certified_gap": 0,
        "verified_nodes": outcome.verified_nodes,
    }


def check_certificate(
    instance: Instance,
    certificate: Any,
    *,
    total_weight: int,
    base_lower_bound: int,
) -> dict[str, Any]:
    """Verify optional WVC dual or BnB proof-tree certificate independently."""
    if certificate is None:
        return {"status": "absent"}
    try:
        if not isinstance(certificate, Mapping):
            raise ValueError("Certificate must be a mapping")
        if type(certificate.get("schema_version")) is not int or certificate["schema_version"] != 1:
            raise ValueError("Unsupported certificate schema_version")
        method = certificate.get("method")
        if method == VALID_INEQUALITY_METHOD:
            return _check_valid_inequality_dual(
                instance, certificate, total_weight=total_weight, base_lower_bound=base_lower_bound,
            )
        if method == BNB_TREE_METHOD:
            return _check_bnb_tree(instance, certificate, total_weight=total_weight)
        raise ValueError(f"Unknown WVC certificate method: {method!r}")
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "rejected", "reason": str(error)}
