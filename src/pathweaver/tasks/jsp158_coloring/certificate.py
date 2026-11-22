"""Solver-independent finite lower-bound and algebraic certificates for JSP-000158.

Supports:
1. ``coloring_lower_bound_tree``: Exhaustive backtracking unsatisfiability witness
   proving no valid (k-1)-coloring exists on a chosen subset of positions in [1, N]
   (so h(N) >= k), promoting tight solutions to FINITE_OPTIMAL or CERTIFIED_BOUND.
2. ``q121_mixed_curve_certificate``: Delegates to the F_121 mixed-curve witness checker.
"""
from collections.abc import Mapping
from typing import Any

from pathweaver.core.contracts import EvidenceLevel
from .q121_certificate import verify_certificate as verify_q121


LOWER_BOUND_TREE_METHOD = "coloring_lower_bound_tree"
Q121_METHOD = "q121_mixed_curve_certificate"


def _has_4ap_violation(assign: dict[int, int], aps_on_subset: list[tuple[int, int, int, int]]) -> bool:
    for a, b, c, d in aps_on_subset:
        ca = assign.get(a)
        if ca is None:
            continue
        cb = assign.get(b)
        if cb is None:
            continue
        cc = assign.get(c)
        if cc is None:
            continue
        cd = assign.get(d)
        if cd is None:
            continue
        if len({ca, cb, cc, cd}) < 3:
            return True
    return False


def _verify_lower_bound_tree(
    n: int,
    cert: Mapping[str, Any],
    *,
    color_count: int,
    base_lower_bound: int,
    max_nodes: int = 200_000,
) -> dict[str, Any]:
    allowed = {"schema_version", "method", "lower_bound_colors", "positions", "tree"}
    if set(cert) != allowed:
        raise ValueError("Unexpected fields in coloring_lower_bound_tree certificate")
    lb = cert["lower_bound_colors"]
    if type(lb) is not int or lb < 2 or lb > n:
        raise ValueError("lower_bound_colors must be an integer in [2, N]")
    positions = cert["positions"]
    if (
        not isinstance(positions, list)
        or not positions
        or len(set(positions)) != len(positions)
        or any(type(p) is not int or not 0 <= p < n for p in positions)
    ):
        raise ValueError("positions must list unique 0-based indices in [0, N-1]")

    pos_set = set(positions)
    # Reconstruct ALL 4-APs completely contained within `positions`.
    aps_on_subset: list[tuple[int, int, int, int]] = []
    for step in range(1, (n - 1) // 3 + 1):
        for start in range(n - 3 * step):
            quad = (start, start + step, start + 2 * step, start + 3 * step)
            if all(q in pos_set for q in quad):
                aps_on_subset.append(quad)

    # Verify exhaustive (lb - 1)-coloring UNSAT tree with canonical symmetry breaking (color <= max_used + 1).
    max_colors = lb - 1
    visited = 0
    stack: list[tuple[Mapping[str, Any], dict[int, int], int]] = [(cert["tree"], {}, 0)]
    while stack:
        node, assign, next_fresh = stack.pop()
        visited += 1
        if visited > max_nodes:
            raise ValueError(f"Coloring UNSAT proof tree exceeds {max_nodes} nodes")
        if not isinstance(node, Mapping):
            raise ValueError("Tree node must be an object")
        kind = node.get("kind")
        if kind == "conflict":
            if not _has_4ap_violation(assign, aps_on_subset):
                raise ValueError("Leaf marked conflict still has no 4-AP violation")
        elif kind == "branch":
            pos = node.get("pos")
            children = node.get("children")
            if pos not in pos_set or pos in assign:
                raise ValueError(f"Invalid or already-assigned branch position: {pos!r}")
            # Symmetry breaking: only color choices 0 .. min(max_colors - 1, next_fresh) are needed.
            expected_colors = list(range(min(max_colors, next_fresh + 1)))
            if not isinstance(children, list) or len(children) != len(expected_colors):
                raise ValueError(
                    f"Branch at pos={pos} must cover all {len(expected_colors)} symmetry-broken colors"
                )
            for color_val, child in zip(expected_colors, children):
                nxt_assign = dict(assign)
                nxt_assign[pos] = color_val
                nxt_fresh = max(next_fresh, color_val + 1)
                stack.append((child, nxt_assign, nxt_fresh))
        else:
            raise ValueError(f"Unknown coloring tree node kind: {kind!r}")

    effective_lb = max(base_lower_bound, lb)
    if lb > color_count:
        raise ValueError(f"Soundness error: certified lower bound {lb} > feasible coloring {color_count}")
    evidence = (
        EvidenceLevel.FINITE_OPTIMAL.value
        if color_count == effective_lb
        else EvidenceLevel.CERTIFIED_BOUND.value
        if effective_lb > base_lower_bound
        else EvidenceLevel.EXPERIMENTAL.value
    )
    return {
        "status": "verified",
        "method": LOWER_BOUND_TREE_METHOD,
        "evidence": evidence,
        "certified_lower_bound": effective_lb,
        "verified_nodes": visited,
        "certified_gap": color_count - effective_lb,
    }


def check_certificate(
    n: int,
    certificate: Any,
    *,
    color_count: int,
    base_lower_bound: int,
) -> dict[str, Any]:
    """Independently check optional JSP-000158 lower-bound or algebraic certificates."""
    if certificate is None:
        return {"status": "absent"}
    try:
        if not isinstance(certificate, Mapping):
            raise ValueError("Certificate must be a mapping")
        method = certificate.get("method")
        if method == LOWER_BOUND_TREE_METHOD:
            if type(certificate.get("schema_version")) is not int or certificate["schema_version"] != 1:
                raise ValueError("Unsupported certificate schema_version")
            return _verify_lower_bound_tree(
                n, certificate, color_count=color_count, base_lower_bound=base_lower_bound,
            )
        if method == Q121_METHOD or certificate.get("problem") == "jsp158_q121_mixed_frobenius_cubic_norm_curve":
            res = verify_q121(dict(certificate))
            return {
                "status": res["status"],
                "method": Q121_METHOD,
                "evidence": EvidenceLevel.CERTIFIED_BOUND.value,
                "certified_lower_bound": base_lower_bound,
                "details": res,
            }
        raise ValueError(f"Unknown JSP-000158 certificate method: {method!r}")
    except (ValueError, TypeError, KeyError) as error:
        return {"status": "rejected", "reason": str(error)}
