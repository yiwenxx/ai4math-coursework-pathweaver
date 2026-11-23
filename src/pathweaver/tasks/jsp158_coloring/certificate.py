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
CYCLIC_ABBA_UNSAT_METHOD = "cyclic_abba_unsat_tree"


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


def _independent_cyclic_propagate(
    m: int,
    r: int,
    aps: list[tuple[int, int, int, int]],
    assign: dict[int, int],
) -> tuple[dict[int, int], bool]:
    """Solver-independent fixed-point 4-AP unit propagation on Z/mZ."""
    full_mask = (1 << r) - 1
    dom = [full_mask] * m
    closed = dict(assign)
    for pos, col in closed.items():
        if type(pos) is not int or not 0 <= pos < m or type(col) is not int or not 0 <= col < r:
            return closed, True
        dom[pos] = 1 << col

    changed = True
    while changed:
        changed = False
        for p0, p1, p2, p3 in aps:
            c0 = closed.get(p0)
            c1 = closed.get(p1)
            c2 = closed.get(p2)
            c3 = closed.get(p3)

            outer_equal = (p0 == p3) or (c0 is not None and c0 == c3)
            inner_equal = (p1 == p2) or (c1 is not None and c1 == c2)

            if outer_equal and inner_equal:
                return closed, True

            # 2d == 0 mod m: (p0, p1, p0, p1), so c0 == c1 makes both outer and inner equal
            if p0 == p2 and p1 == p3:
                if c0 is not None and c1 is not None and c0 == c1:
                    return closed, True
                if c0 is not None and c1 is None:
                    bit = 1 << c0
                    if dom[p1] & bit:
                        dom[p1] &= ~bit
                        if dom[p1] == 0:
                            return closed, True
                        if (dom[p1] & (dom[p1] - 1)) == 0:
                            closed[p1] = dom[p1].bit_length() - 1
                            changed = True
                elif c1 is not None and c0 is None:
                    bit = 1 << c1
                    if dom[p0] & bit:
                        dom[p0] &= ~bit
                        if dom[p0] == 0:
                            return closed, True
                        if (dom[p0] & (dom[p0] - 1)) == 0:
                            closed[p0] = dom[p0].bit_length() - 1
                            changed = True
                continue

            if outer_equal:
                if c1 is not None and c2 is None:
                    bit = 1 << c1
                    if dom[p2] & bit:
                        dom[p2] &= ~bit
                        if dom[p2] == 0:
                            return closed, True
                        if (dom[p2] & (dom[p2] - 1)) == 0:
                            closed[p2] = dom[p2].bit_length() - 1
                            changed = True
                elif c2 is not None and c1 is None:
                    bit = 1 << c2
                    if dom[p1] & bit:
                        dom[p1] &= ~bit
                        if dom[p1] == 0:
                            return closed, True
                        if (dom[p1] & (dom[p1] - 1)) == 0:
                            closed[p1] = dom[p1].bit_length() - 1
                            changed = True

            if inner_equal:
                if c0 is not None and c3 is None:
                    bit = 1 << c0
                    if dom[p3] & bit:
                        dom[p3] &= ~bit
                        if dom[p3] == 0:
                            return closed, True
                        if (dom[p3] & (dom[p3] - 1)) == 0:
                            closed[p3] = dom[p3].bit_length() - 1
                            changed = True
                elif c3 is not None and c0 is None:
                    bit = 1 << c3
                    if dom[p0] & bit:
                        dom[p0] &= ~bit
                        if dom[p0] == 0:
                            return closed, True
                        if (dom[p0] & (dom[p0] - 1)) == 0:
                            closed[p0] = dom[p0].bit_length() - 1
                            changed = True

    return closed, False


def verify_cyclic_abba_unsat_tree(
    cert: Mapping[str, Any],
    *,
    max_nodes: int = 250_000,
) -> dict[str, Any]:
    """Zero-trust independent verification of a cyclic ABBA-free UNSAT proof tree."""
    allowed = {
        "schema_version", "method", "m", "palette_limit",
        "symmetry_mode", "root_assign", "use_canonical_sr", "tree",
    }
    if set(cert) != allowed or cert.get("schema_version") != 1 or cert.get("method") != CYCLIC_ABBA_UNSAT_METHOD:
        raise ValueError("Malformed cyclic_abba_unsat_tree certificate header")

    m = cert["m"]
    r = cert["palette_limit"]
    if type(m) is not int or m < 2 or type(r) is not int or r < 1:
        raise ValueError("Invalid m or palette_limit in cyclic_abba_unsat_tree")

    sym = cert["symmetry_mode"]
    raw_root = cert["root_assign"]
    if not isinstance(raw_root, list):
        raise ValueError("root_assign must be a list of [pos, color] pairs")
    root_assign = {int(pair[0]): int(pair[1]) for pair in raw_root}

    if sym == "canonical_sr":
        if root_assign != {0: 0}:
            raise ValueError("canonical_sr requires root_assign == {0: 0}")
    elif sym == "torsion_triangle_sr":
        if m % 3 != 0 or r < 3 or root_assign != {0: 0, m // 3: 1, (2 * m) // 3: 2}:
            raise ValueError("Invalid torsion_triangle_sr root_assign")
    elif sym == "antipodal_edge_sr":
        if m % 2 != 0 or r < 2 or root_assign != {0: 0, m // 2: 1}:
            raise ValueError("Invalid antipodal_edge_sr root_assign")
    elif sym != "custom_root":
        raise ValueError(f"Unknown symmetry_mode: {sym!r}")

    use_sr = bool(cert["use_canonical_sr"])
    aps = [(a, (a + d) % m, (a + 2 * d) % m, (a + 3 * d) % m) for a in range(m) for d in range(1, m)]

    root_fresh = max(root_assign.values(), default=-1) + 1
    visited = 0
    stack: list[tuple[Mapping[str, Any], dict[int, int], int]] = [(cert["tree"], root_assign, root_fresh)]

    while stack:
        node, assign, next_fresh = stack.pop()
        visited += 1
        if visited > max_nodes:
            raise ValueError(f"Cyclic ABBA UNSAT tree exceeds {max_nodes} nodes")
        if not isinstance(node, Mapping):
            raise ValueError("Tree node must be an object")

        closed, conflict = _independent_cyclic_propagate(m, r, aps, assign)
        kind = node.get("kind")
        if kind == "conflict":
            if not conflict:
                raise ValueError("Leaf marked conflict does not reach conflict under 4-AP unit propagation")
        elif kind == "branch":
            if conflict:
                continue
            pos = node.get("pos")
            children = node.get("children")
            if type(pos) is not int or not 0 <= pos < m or pos in closed:
                raise ValueError(f"Invalid or already-assigned branch position: {pos!r}")
            eff_fresh = max(next_fresh, max(closed.values(), default=-1) + 1) if use_sr else r
            expected_count = min(r, eff_fresh + 1) if use_sr else r
            if not isinstance(children, list) or len(children) != expected_count:
                raise ValueError(f"Branch at pos={pos} must cover all {expected_count} colors")
            for col_val, child in enumerate(children):
                nxt = dict(closed)
                nxt[pos] = col_val
                stack.append((child, nxt, max(eff_fresh, col_val + 1)))
        else:
            raise ValueError(f"Unknown cyclic UNSAT tree node kind: {kind!r}")

    return {
        "status": "verified",
        "method": CYCLIC_ABBA_UNSAT_METHOD,
        "evidence": EvidenceLevel.CERTIFIED_BOUND.value,
        "m": m,
        "palette_limit": r,
        "symmetry_mode": sym,
        "verified_nodes": visited,
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
        if method == CYCLIC_ABBA_UNSAT_METHOD:
            return verify_cyclic_abba_unsat_tree(certificate)
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
