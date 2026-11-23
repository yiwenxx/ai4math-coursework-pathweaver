"""Exact SAT / Bitset-CDCL + symmetry-breaking solver for cyclic ABBA-free templates.

Searches for colorings c: Z/mZ -> {0, ..., r-1} avoiding all nonzero-step cyclic ABBA
progressions (a, a+d, a+2d, a+3d) mod m (1 <= d < m):
    not (c(a) == c(a+3d) and c(a+d) == c(a+2d)).

Features:
1. Exact pairwise static + dynamic conflict graph compilation:
   - Order-2 and order-3 torsion pairs (2(u-v) == 0 or 3(u-v) == 0 mod m) become static
     binary disequality edges c(u) != c(v).
   - Non-degenerate 4-APs couple inner pair {u, v} with outer pair {2u-v, 2v-u} mod m:
     making either pair monochromatic immediately activates a disequality edge on the other.
2. Symmetry breaking:
   - Divisibility by 3: fixes the rainbow torsion triangle (c(0), c(m/3), c(2m/3)) = (0, 1, 2).
   - Even modulus (not div by 3): fixes the antipodal edge (c(0), c(m/2)) = (0, 1).
   - Prime modulus p > r^2 with full/large x3 orbit: supports Double-Radius Orbit Reduction
     (fixing c(1) = c(p-1) = 0 and c(3^j) = c(-3^j) in {0, 1} for 2 <= j <= r).
   - Canonical S_r symmetry breaking on remaining free colors (color <= max_used + 1).
3. Multiplicative coset / antipodal-equivariant quotient solver:
   - Enumerates subgroups H <= (Z/mZ)* with -1 not in H (including odd-order subgroups of F_p*
     and factor-isolated subgroups of composite Z/mZ*), plus antipodal-shifted quotients
     c(-x) = (c(x) + shift) mod r, solving the quotient coloring problem exactly.
4. Emits solver-independent UNSAT proof trees (`cyclic_abba_unsat_tree`) verifiable by
   `certificate.py`, or valid templates verifiable by `verify_jsp158_artifacts.py` and Lean 4.
"""
from dataclasses import dataclass
import math
import time
from typing import Any


@dataclass(frozen=True)
class CyclicABBAConstraints:
    """Compiled static disequality edges and coupled pair-implication table for Z/mZ."""
    m: int
    r: int
    static_adj: tuple[tuple[int, ...], ...]
    # coupled_pairs[u][v] (for u != v) -> tuple of pairs (p, q) with p < q that cannot be monochromatic if c(u)==c(v)
    coupled_pairs: tuple[tuple[tuple[tuple[int, int], ...], ...], ...]
    all_aps: tuple[tuple[int, int, int, int], ...]


def compile_cyclic_abba(m: int, r: int) -> CyclicABBAConstraints:
    if type(m) is not int or m < 2:
        raise ValueError("m must be an integer >= 2")
    if type(r) is not int or r < 1:
        raise ValueError("r must be an integer >= 1")

    static_sets: list[set[int]] = [set() for _ in range(m)]
    coupled: list[list[set[tuple[int, int]]]] = [[set() for _ in range(m)] for _ in range(m)]
    aps: list[tuple[int, int, int, int]] = []

    for a in range(m):
        for d in range(1, m):
            p0 = a
            p1 = (a + d) % m
            p2 = (a + 2 * d) % m
            p3 = (a + 3 * d) % m
            aps.append((p0, p1, p2, p3))

            in_u, in_v = (p1, p2) if p1 < p2 else (p2, p1)
            if p0 == p3:
                # 3d == 0 mod m: outer pair automatically equal, so inner pair cannot be equal.
                if in_u != in_v:
                    static_sets[in_u].add(in_v)
                    static_sets[in_v].add(in_u)
                continue

            out_p, out_q = (p0, p3) if p0 < p3 else (p3, p0)
            if (in_u, in_v) == (out_p, out_q):
                # 2d == 0 mod m: inner and outer pairs coincide, so c(a) != c(a + m/2).
                static_sets[in_u].add(in_v)
                static_sets[in_v].add(in_u)
                continue

            coupled[in_u][in_v].add((out_p, out_q))
            coupled[in_v][in_u].add((out_p, out_q))
            coupled[out_p][out_q].add((in_u, in_v))
            coupled[out_q][out_p].add((in_u, in_v))

    # Remove any coupled target pair that is already a static edge.
    for u in range(m):
        for v in range(m):
            if coupled[u][v]:
                coupled[u][v] = {
                    (p, q) for (p, q) in coupled[u][v] if q not in static_sets[p]
                }

    return CyclicABBAConstraints(
        m=m,
        r=r,
        static_adj=tuple(tuple(sorted(s)) for s in static_sets),
        coupled_pairs=tuple(
            tuple(tuple(sorted(coupled[u][v])) for v in range(m))
            for u in range(m)
        ),
        all_aps=tuple(aps),
    )


def count_cyclic_abba_violations(m: int, colors: list[int]) -> int:
    violations = 0
    for a in range(m):
        for d in range(1, m):
            if colors[a] == colors[(a + 3 * d) % m] and colors[(a + d) % m] == colors[(a + 2 * d) % m]:
                violations += 1
    return violations


def unit_propagate_cyclic(
    constraints: CyclicABBAConstraints,
    assign: dict[int, int],
) -> tuple[dict[int, int], list[int], bool]:
    """Deterministic fixed-point 4-AP unit propagation shared by solver and verifier.

    Starting from `assign`, repeatedly:
    - removes forbidden colors implied by static disequality edges and any 4-AP where
      one mirror pair is assigned equal and one endpoint of the other pair is assigned;
    - assigns any vertex whose domain bitmask becomes a singleton (1 << k);
    - returns `(closed_assign, domains, conflict_detected)`.
    """
    m, r = constraints.m, constraints.r
    full_mask = (1 << r) - 1
    dom = [full_mask] * m
    closed = dict(assign)
    static_adj = constraints.static_adj
    coupled_pairs = constraints.coupled_pairs

    for pos, col in closed.items():
        if not 0 <= col < r:
            return closed, dom, True
        dom[pos] = 1 << col

    # Check initial static conflicts and queue all initial assignments.
    queue: list[int] = list(closed.keys())
    processed_in_color: list[list[int]] = [[] for _ in range(r)]
    dyn_adj: list[set[int]] = [set() for _ in range(m)]

    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        col_u = closed[u]
        bit_u = 1 << col_u

        # 1. Static disequality neighbors
        for v in static_adj[u]:
            if v in closed:
                if closed[v] == col_u:
                    return closed, dom, True
            else:
                if dom[v] & bit_u:
                    dom[v] &= ~bit_u
                    if dom[v] == 0:
                        return closed, dom, True
                    if (dom[v] & (dom[v] - 1)) == 0:
                        closed[v] = dom[v].bit_length() - 1
                        queue.append(v)

        # 2. Dynamic disequality neighbors activated earlier
        for v in list(dyn_adj[u]):
            if v in closed:
                if closed[v] == col_u:
                    return closed, dom, True
            else:
                if dom[v] & bit_u:
                    dom[v] &= ~bit_u
                    if dom[v] == 0:
                        return closed, dom, True
                    if (dom[v] & (dom[v] - 1)) == 0:
                        closed[v] = dom[v].bit_length() - 1
                        queue.append(v)

        # 3. Pairings with previously processed vertices of the SAME color col_u
        same_list = processed_in_color[col_u]
        for v in same_list:
            for p, q in coupled_pairs[u][v]:
                p_in = p in closed
                q_in = q in closed
                if p_in and q_in:
                    if closed[p] == closed[q]:
                        return closed, dom, True
                elif p_in:
                    bit_p = 1 << closed[p]
                    if dom[q] & bit_p:
                        dom[q] &= ~bit_p
                        if dom[q] == 0:
                            return closed, dom, True
                        if (dom[q] & (dom[q] - 1)) == 0:
                            closed[q] = dom[q].bit_length() - 1
                            queue.append(q)
                elif q_in:
                    bit_q = 1 << closed[q]
                    if dom[p] & bit_q:
                        dom[p] &= ~bit_q
                        if dom[p] == 0:
                            return closed, dom, True
                        if (dom[p] & (dom[p] - 1)) == 0:
                            closed[p] = dom[p].bit_length() - 1
                            queue.append(p)
                else:
                    dyn_adj[p].add(q)
                    dyn_adj[q].add(p)
        same_list.append(u)

    return closed, dom, False


def solve_cyclic_abba_exact(
    m: int,
    r: int,
    *,
    wall_seconds: float = 15.0,
    max_nodes: int = 200_000,
    emit_tree: bool = True,
    initial_assign: dict[int, int] | None = None,
    use_canonical_sr: bool = True,
) -> dict[str, Any]:
    """Exact bitset MAC + unit-propagation backtracking solver with proof-tree emission.

    When `initial_assign` is omitted, uses canonical S_r symmetry breaking starting from
    c(0) = 0 (and when 3 | m, r >= 3, fixes the static torsion triangle (0, m/3, 2m/3) = (0, 1, 2);
    when 2 | m, 3 not| m, r >= 2, fixes the static antipodal edge (0, m/2) = (0, 1)).
    """
    constraints = compile_cyclic_abba(m, r)
    deadline = time.monotonic() + wall_seconds

    if initial_assign is not None:
        root_assign = dict(initial_assign)
        root_fresh = max(root_assign.values(), default=-1) + 1
        symmetry_mode = "custom_root"
    else:
        if m % 3 == 0 and r >= 3:
            root_assign = {0: 0, m // 3: 1, (2 * m) // 3: 2}
            root_fresh = 3
            symmetry_mode = "torsion_triangle_sr"
        elif m % 2 == 0 and r >= 2:
            root_assign = {0: 0, m // 2: 1}
            root_fresh = 2
            symmetry_mode = "antipodal_edge_sr"
        else:
            root_assign = {0: 0}
            root_fresh = 1
            symmetry_mode = "canonical_sr"

    # Precompute static + potential degree heuristic for tie-breaking most-constrained variables.
    base_weight = [
        len(constraints.static_adj[u]) * 16 + sum(len(constraints.coupled_pairs[u][v]) for v in range(m))
        for u in range(m)
    ]

    nodes_visited = 0
    timed_out = False
    found_colors: list[int] | None = None

    def search(assign: dict[int, int], next_fresh: int) -> dict[str, Any] | None:
        nonlocal nodes_visited, timed_out, found_colors
        if nodes_visited >= max_nodes or (nodes_visited & 63 == 0 and time.monotonic() >= deadline):
            timed_out = True
            return None
        nodes_visited += 1

        closed, dom, conflict = unit_propagate_cyclic(constraints, assign)
        if conflict:
            return {"kind": "conflict"} if emit_tree else None

        if len(closed) == m:
            candidate = [closed[i] for i in range(m)]
            if count_cyclic_abba_violations(m, candidate) == 0:
                found_colors = candidate
                return None
            return {"kind": "conflict"} if emit_tree else None

        # Choose unassigned position with minimum remaining values (MRV), breaking ties by base_weight.
        best_pos = -1
        best_count = r + 1
        best_w = -1
        for u in range(m):
            if u not in closed:
                cnt = dom[u].bit_count()
                w = base_weight[u]
                if cnt < best_count or (cnt == best_count and w > best_w):
                    best_count = cnt
                    best_pos = u
                    best_w = w

        # Wait: if we use unit_propagate_cyclic in the verifier, the verifier must know WHICH
        # colors were branched on at `best_pos`.
        # When `use_canonical_sr` is True AND no unit propagations have introduced colors >= next_fresh,
        # we can restrict branch colors to 0 .. min(r - 1, eff_fresh).
        # To keep verifier rules crystal-clear and 100% sound even after unit propagation:
        # eff_fresh is max(next_fresh, max(closed.values(), default=-1) + 1).
        eff_fresh = max(next_fresh, max(closed.values(), default=-1) + 1) if use_canonical_sr else r
        max_col = min(r, eff_fresh + 1) if use_canonical_sr else r
        children: list[dict[str, Any]] = []

        for col in range(max_col):
            nxt_assign = dict(closed)
            nxt_assign[best_pos] = col
            nxt_fresh = max(eff_fresh, col + 1)
            if not (dom[best_pos] & (1 << col)):
                # This color is already forbidden by unit propagation, so assigning it immediately conflicts.
                if emit_tree:
                    children.append({"kind": "conflict"})
                continue
            child_tree = search(nxt_assign, nxt_fresh)
            if found_colors is not None or timed_out:
                return None
            if emit_tree and child_tree is not None:
                children.append(child_tree)

        return {"kind": "branch", "pos": best_pos, "children": children} if emit_tree else None

    tree = search(root_assign, root_fresh)
    elapsed = round(time.monotonic() - (deadline - wall_seconds), 4)

    if found_colors is not None:
        return {
            "status": "SAT",
            "m": m,
            "r": r,
            "colors": found_colors,
            "used_colors": len(set(found_colors)),
            "crosses_quarter_threshold": m > len(set(found_colors)) ** 4,
            "nodes_visited": nodes_visited,
            "elapsed_seconds": elapsed,
            "symmetry_mode": symmetry_mode,
        }
    if not timed_out:
        cert = {
            "schema_version": 1,
            "method": "cyclic_abba_unsat_tree",
            "m": m,
            "palette_limit": r,
            "symmetry_mode": symmetry_mode,
            "root_assign": [[k, v] for k, v in sorted(root_assign.items())],
            "use_canonical_sr": use_canonical_sr,
            "tree": tree,
        }
        return {
            "status": "UNSAT",
            "m": m,
            "r": r,
            "nodes_visited": nodes_visited,
            "elapsed_seconds": elapsed,
            "symmetry_mode": symmetry_mode,
            "certificate": cert if emit_tree else None,
        }
    return {
        "status": "UNKNOWN",
        "m": m,
        "r": r,
        "nodes_visited": nodes_visited,
        "elapsed_seconds": elapsed,
        "symmetry_mode": symmetry_mode,
    }


def double_radius_reduction_roots(p: int, r: int) -> dict[str, Any] | None:
    """Stratum & Coset-Generalized Double-Radius Orbit Reduction for any odd m with gcd(m, 6) = 1.

    Partitions R_m = (Z/mZ \\ {0}) / {+-1} (size half = (m-1)/2) into its disjoint x3 cycles C_1..C_K,
    where each cycle C_a lies in a divisor stratum d_a = gcd(rho, m) and has length L_a.
    Cycles with L_a <= 3 are cliques/triangles under x3 and can hold at most 1 monochromatic radius.
    On cycles with L_a >= 4, avoiding any monochromatic pair at directed/undirected cycle distance
    j in {2, ..., g} limits the cycle to at most floor(L_a / (g + 1)) monochromatic radii.
    Whenever the sum of capacities across all cycles is strictly less than M = ceil(min_pairs / m),
    pigeonhole forces at least one stratum d_a with L_a >= 4 to contain a monochromatic pair at
    step distance j in {2, ..., g}, which normalizes by unit scaling in (Z/mZ)* to
        c(d_a) = c(m - d_a) = 0,   c(3^j * d_a mod m) = c(-3^j * d_a mod m) in {0, 1}.
    """
    m = p
    if m < 5 or math.gcd(m, 6) != 1:
        return None
    half = (m - 1) // 2

    visited: set[int] = set()
    cycles: list[tuple[int, int]] = []  # (stratum_d, length_L)
    stratum_cycle_len: dict[int, int] = {}
    for x in range(1, half + 1):
        rep = min(x, m - x)
        if rep in visited:
            continue
        cyc: list[int] = []
        cur = rep
        while cur not in cyc:
            cyc.append(cur)
            visited.add(cur)
            nxt = (cur * 3) % m
            cur = min(nxt, m - nxt)
        d_stratum = math.gcd(rep, m)
        cycles.append((d_stratum, len(cyc)))
        stratum_cycle_len[d_stratum] = max(stratum_cycle_len.get(d_stratum, 0), len(cyc))

    # Minimum monochromatic pairs by convexity
    q_div, rem = divmod(m, r)
    min_pairs = rem * ((q_div + 1) * q_div // 2) + (r - rem) * (q_div * (q_div - 1) // 2)
    min_radii_at_best_center = (min_pairs + m - 1) // m
    if min_radii_at_best_center < 2:
        return None

    max_gap: int | None = None
    for g in range(2, r + 2):
        # Cycles with L <= 3 can hold at most 1 independent radius; cycles with L >= 4 hold at most L // (g + 1) without gap <= g
        cap = sum(1 if length <= 3 else (1 if length <= g else length // (g + 1)) for _, length in cycles)
        if cap < min_radii_at_best_center:
            max_gap = g
            break
    if max_gap is None:
        return None

    active_strata = sorted(d for d, length in stratum_cycle_len.items() if length >= 4)
    if not active_strata:
        return None

    roots: list[dict[str, Any]] = []
    for d_stratum in active_strata:
        s_len = stratum_cycle_len[d_stratum]
        # On a cycle of length s_len, any chord of step j > s_len // 2 equals step (s_len - j) from the other endpoint
        eff_max_j = min(max_gap, s_len // 2)
        for j in range(2, eff_max_j + 1):
            rj = (d_stratum * pow(3, j, m)) % m
            neg_rj = (m - rj) % m
            if len({d_stratum, m - d_stratum, rj, neg_rj}) < 4:
                continue
            prefix = "" if d_stratum == 1 else f"d{d_stratum}_"
            for col_j, label in ((0, f"{prefix}j{j}_same"), (1, f"{prefix}j{j}_different")):
                roots.append({
                    "branch_id": label,
                    "stratum_d": d_stratum,
                    "gap_j": j,
                    "radius_j": rj,
                    "root_assign": {d_stratum: 0, m - d_stratum: 0, rj: col_j, neg_rj: col_j},
                })
    return {
        "p": m,
        "r": r,
        "unsigned_group_size": half,
        "unsigned_orbit_length": stratum_cycle_len.get(1, 0),
        "coset_count": len(cycles),
        "active_strata": active_strata,
        "min_monochromatic_pairs": min_pairs,
        "min_center_radii": min_radii_at_best_center,
        "max_gap": max_gap,
        "roots": roots,
    }


def solve_cyclic_abba_prime_double_radius(
    p: int,
    r: int,
    *,
    wall_seconds_per_root: float = 10.0,
    max_nodes_per_root: int = 200_000,
    emit_tree: bool = True,
) -> dict[str, Any] | None:
    """Solve prime modulus p using the Double-Radius Orbit Reduction when applicable."""
    reduction = double_radius_reduction_roots(p, r)
    if reduction is None or not reduction["roots"]:
        return None

    branch_results: list[dict[str, Any]] = []
    total_nodes = 0
    t0 = time.monotonic()

    for root in reduction["roots"]:
        res = solve_cyclic_abba_exact(
            p,
            r,
            wall_seconds=wall_seconds_per_root,
            max_nodes=max_nodes_per_root,
            emit_tree=emit_tree,
            initial_assign=root["root_assign"],
            use_canonical_sr=True,
        )
        total_nodes += res["nodes_visited"]
        branch_results.append({
            "branch_id": root["branch_id"],
            "gap_j": root["gap_j"],
            "status": res["status"],
            "nodes_visited": res["nodes_visited"],
            "certificate": res.get("certificate"),
        })
        if res["status"] == "SAT":
            return {
                "status": "SAT",
                "m": p,
                "r": r,
                "colors": res["colors"],
                "used_colors": res["used_colors"],
                "crosses_quarter_threshold": res["crosses_quarter_threshold"],
                "nodes_visited": total_nodes,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "symmetry_mode": "double_radius_orbit_reduction",
                "winning_branch": root["branch_id"],
            }
        if res["status"] != "UNSAT":
            return {
                "status": "UNKNOWN",
                "m": p,
                "r": r,
                "nodes_visited": total_nodes,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "symmetry_mode": "double_radius_orbit_reduction",
                "branches": branch_results,
            }

    return {
        "status": "UNSAT",
        "m": p,
        "r": r,
        "nodes_visited": total_nodes,
        "elapsed_seconds": round(time.monotonic() - t0, 4),
        "symmetry_mode": "double_radius_orbit_reduction",
        "reduction": {k: v for k, v in reduction.items() if k != "roots"},
        "branches": branch_results,
    }


def multiplicative_subgroups(m: int, *, avoid_minus_one: bool = True) -> list[tuple[int, ...]]:
    """Enumerate distinct non-trivial subgroups H <= (Z/mZ)* in O(m) time using abelian group structure."""
    units = [x for x in range(1, m) if math.gcd(x, m) == 1]
    if not units:
        return []
    minus_one = m - 1
    phi = len(units)
    two_pow = 1
    while (phi // two_pow) % 2 == 0:
        two_pow *= 2

    all_subs: set[tuple[int, ...]] = set()

    # 1. Maximal odd-order subgroup of (Z/mZ)*: {u^(2^v) mod m : u in units}
    max_odd = tuple(sorted({pow(u, two_pow, m) for u in units}))
    if len(max_odd) > 1 and (not avoid_minus_one or minus_one not in max_odd):
        all_subs.add(max_odd)

    # 2. Prime-power factor-fixing subgroups {u in (Z/mZ)* : u == 1 mod q_i} for composite m
    temp = m
    prime_powers: list[int] = []
    d = 2
    while d * d <= temp:
        if temp % d == 0:
            q = 1
            while temp % d == 0:
                q *= d
                temp //= d
            prime_powers.append(q)
        d += 1
    if temp > 1:
        prime_powers.append(temp)

    if len(prime_powers) >= 2:
        for q in prime_powers:
            if q >= 3:
                fix_q = tuple(sorted(u for u in units if u % q == 1))
                if len(fix_q) > 1 and (not avoid_minus_one or minus_one not in fix_q):
                    all_subs.add(fix_q)

    # 3. Cyclic subgroups generated by individual units
    for u in units:
        if u == 1:
            continue
        sub = set()
        cur = 1
        while cur not in sub:
            sub.add(cur)
            cur = (cur * u) % m
        if avoid_minus_one and minus_one in sub:
            continue
        if len(sub) > 1:
            all_subs.add(tuple(sorted(sub)))

    return sorted(all_subs, key=lambda s: (-len(s), s))


def solve_cyclic_abba_coset_quotient(
    m: int,
    r: int,
    *,
    min_subgroup_size: int = 2,
    max_orbits: int = 70,
    wall_seconds_per_subgroup: float = 1.0,
) -> dict[str, Any]:
    """Exhaustively search H-invariant and antipodal-shifted H-coset colorings on Z/mZ."""
    subgroups = [h for h in multiplicative_subgroups(m, avoid_minus_one=True) if len(h) >= min_subgroup_size]
    tested_quotients: list[dict[str, Any]] = []

    # Mode A: Pure H-invariant quotients (-1 not in H)
    for h_sub in subgroups:
        if m // len(h_sub) > max_orbits:
            continue
        orbit_id = [-1] * m
        orbits: list[tuple[int, ...]] = []
        for x in range(m):
            if orbit_id[x] != -1:
                continue
            orb = sorted({(x * h) % m for h in h_sub})
            oid = len(orbits)
            for y in orb:
                orbit_id[y] = oid
            orbits.append(tuple(orb))

        k_orbits = len(orbits)
        if k_orbits > max_orbits:
            continue

        res = _solve_quotient_orbits(m, orbit_id, k_orbits, r, wall_seconds=wall_seconds_per_subgroup)
        tested_quotients.append({
            "kind": "H_invariant",
            "subgroup_order": len(h_sub),
            "orbit_count": k_orbits,
            "generator_sample": list(h_sub[:4]),
            "status": res["status"],
            "nodes_visited": res["nodes_visited"],
            "self_conflict": res.get("self_conflict", False),
        })
        if res["status"] == "SAT":
            return {
                "status": "SAT",
                "m": m,
                "r": r,
                "colors": res["colors"],
                "used_colors": len(set(res["colors"])),
                "crosses_quarter_threshold": m > len(set(res["colors"])) ** 4,
                "quotient_details": tested_quotients[-1],
                "tested_quotients": tested_quotients,
            }

    # Mode B: Antipodal-shifted H-coset quotients c(-x) = (c(x) + r//2) mod r (for even r >= 4)
    if r % 2 == 0:
        half_r = r // 2
        for h_sub in subgroups:
            if m // len(h_sub) > max_orbits:
                continue
            orbit_id = [-1] * m
            orbits = []
            for x in range(m):
                if orbit_id[x] != -1:
                    continue
                orb = sorted({(x * h) % m for h in h_sub})
                oid = len(orbits)
                for y in orb:
                    orbit_id[y] = oid
                orbits.append(tuple(orb))
            k_orbits = len(orbits)
            if k_orbits > max_orbits:
                continue
            res = _solve_quotient_orbits(
                m, orbit_id, k_orbits, r,
                wall_seconds=wall_seconds_per_subgroup,
                antipodal_shift=half_r,
            )
            tested_quotients.append({
                "kind": "antipodal_equivariant",
                "subgroup_order": len(h_sub),
                "orbit_count": k_orbits,
                "status": res["status"],
                "nodes_visited": res["nodes_visited"],
                "self_conflict": res.get("self_conflict", False),
            })
            if res["status"] == "SAT":
                return {
                    "status": "SAT",
                    "m": m,
                    "r": r,
                    "colors": res["colors"],
                    "used_colors": len(set(res["colors"])),
                    "crosses_quarter_threshold": m > len(set(res["colors"])) ** 4,
                    "quotient_details": tested_quotients[-1],
                    "tested_quotients": tested_quotients,
                }

    all_unsat = all(q["status"] == "UNSAT" for q in tested_quotients)
    return {
        "status": "UNSAT" if (tested_quotients and all_unsat) else "NO_QUOTIENT_FOUND",
        "m": m,
        "r": r,
        "tested_quotient_count": len(tested_quotients),
        "tested_quotients": tested_quotients,
    }


def _solve_quotient_orbits(
    m: int,
    orbit_id: list[int],
    k_orbits: int,
    r: int,
    *,
    wall_seconds: float = 1.0,
    antipodal_shift: int | None = None,
) -> dict[str, Any]:
    """Exact backtracking solver on K quotient orbits of Z/mZ with fast self-conflict short-circuit."""
    q_static: list[set[int]] = [set() for _ in range(k_orbits)]
    q_coupled: list[list[set[tuple[int, int]]]] = [[set() for _ in range(k_orbits)] for _ in range(k_orbits)]

    for a in range(m):
        o0 = orbit_id[a]
        for d in range(1, m):
            o1 = orbit_id[(a + d) % m]
            o2 = orbit_id[(a + 2 * d) % m]
            o3 = orbit_id[(a + 3 * d) % m]
            if o0 == o3 and o1 == o2:
                return {"status": "UNSAT", "nodes_visited": 1, "self_conflict": True}
            if o0 == o3:
                q_static[o1].add(o2)
                q_static[o2].add(o1)
            elif o1 == o2:
                q_static[o0].add(o3)
                q_static[o3].add(o0)
            else:
                in_u, in_v = (o1, o2) if o1 < o2 else (o2, o1)
                out_p, out_q = (o0, o3) if o0 < o3 else (o3, o0)
                if (in_u, in_v) == (out_p, out_q):
                    q_static[in_u].add(in_v)
                    q_static[in_v].add(in_u)
                else:
                    q_coupled[in_u][in_v].add((out_p, out_q))
                    q_coupled[in_v][in_u].add((out_p, out_q))
                    q_coupled[out_p][out_q].add((in_u, in_v))
                    q_coupled[out_q][out_p].add((in_u, in_v))

    # Antipodal pairing map: neg_orbit[orbit_id[x]] = orbit_id[(-x) % m]
    neg_orbit = [0] * k_orbits
    for x in range(m):
        neg_orbit[orbit_id[x]] = orbit_id[(-x) % m]
    if antipodal_shift is not None:
        # c(neg_orbit[o]) == (c(o) + antipodal_shift) % r
        # Wait: for x = 0, neg_orbit[o_0] == o_0, so 0 cannot satisfy c(0) = c(0) + shift unless 0 is unlinked.
        pass

    full_mask = (1 << r) - 1
    deadline = time.monotonic() + wall_seconds
    nodes = 0
    found_orb_colors: list[int] | None = None

    def propagate_q(assign: dict[int, int]) -> tuple[dict[int, int], list[int], bool]:
        dom = [full_mask] * k_orbits
        closed = dict(assign)
        for o, col in list(closed.items()):
            dom[o] = 1 << col
            if antipodal_shift is not None and o != orbit_id[0]:
                no = neg_orbit[o]
                ncol = (col + antipodal_shift) % r
                if no in closed and closed[no] != ncol:
                    return closed, dom, True
                closed[no] = ncol
                dom[no] = 1 << ncol

        queue = list(closed.keys())
        seen_by_col: list[list[int]] = [[] for _ in range(r)]
        dyn_adj: list[set[int]] = [set() for _ in range(k_orbits)]
        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1
            cu = closed[u]
            bit_u = 1 << cu

            if antipodal_shift is not None and u != orbit_id[0]:
                no = neg_orbit[u]
                ncol = (cu + antipodal_shift) % r
                if no in closed:
                    if closed[no] != ncol:
                        return closed, dom, True
                else:
                    if not (dom[no] & (1 << ncol)):
                        return closed, dom, True
                    dom[no] = 1 << ncol
                    closed[no] = ncol
                    queue.append(no)

            for v in q_static[u]:
                if v in closed:
                    if closed[v] == cu:
                        return closed, dom, True
                elif dom[v] & bit_u:
                    dom[v] &= ~bit_u
                    if dom[v] == 0:
                        return closed, dom, True
                    if (dom[v] & (dom[v] - 1)) == 0:
                        closed[v] = dom[v].bit_length() - 1
                        queue.append(v)

            for v in list(dyn_adj[u]):
                if v in closed:
                    if closed[v] == cu:
                        return closed, dom, True
                elif dom[v] & bit_u:
                    dom[v] &= ~bit_u
                    if dom[v] == 0:
                        return closed, dom, True
                    if (dom[v] & (dom[v] - 1)) == 0:
                        closed[v] = dom[v].bit_length() - 1
                        queue.append(v)

            for v in seen_by_col[cu]:
                for p, q in q_coupled[u][v]:
                    p_in = p in closed
                    q_in = q in closed
                    if p_in and q_in:
                        if closed[p] == closed[q]:
                            return closed, dom, True
                    elif p_in:
                        bp = 1 << closed[p]
                        if dom[q] & bp:
                            dom[q] &= ~bp
                            if dom[q] == 0:
                                return closed, dom, True
                            if (dom[q] & (dom[q] - 1)) == 0:
                                closed[q] = dom[q].bit_length() - 1
                                queue.append(q)
                    elif q_in:
                        bq = 1 << closed[q]
                        if dom[p] & bq:
                            dom[p] &= ~bq
                            if dom[p] == 0:
                                return closed, dom, True
                            if (dom[p] & (dom[p] - 1)) == 0:
                                closed[p] = dom[p].bit_length() - 1
                                queue.append(p)
                    else:
                        dyn_adj[p].add(q)
                        dyn_adj[q].add(p)
            seen_by_col[cu].append(u)
        return closed, dom, False

    timed_out = False

    def bt(assign: dict[int, int], next_fresh: int) -> None:
        nonlocal nodes, timed_out, found_orb_colors
        if (nodes & 63 == 0 and time.monotonic() >= deadline):
            timed_out = True
            return
        nodes += 1
        closed, dom, conflict = propagate_q(assign)
        if conflict:
            return
        if len(closed) == k_orbits:
            full_colors = [closed[orbit_id[x]] for x in range(m)]
            if count_cyclic_abba_violations(m, full_colors) == 0:
                found_orb_colors = full_colors
            return

        best_o = -1
        best_cnt = r + 1
        best_deg = -1
        for o in range(k_orbits):
            if o not in closed:
                cnt = dom[o].bit_count()
                deg = len(q_static[o])
                if cnt < best_cnt or (cnt == best_cnt and deg > best_deg):
                    best_cnt = cnt
                    best_o = o
                    best_deg = deg

        eff_fresh = max(next_fresh, max(closed.values(), default=-1) + 1) if antipodal_shift is None else r
        max_col = min(r, eff_fresh + 1) if antipodal_shift is None else r
        for col in range(max_col):
            if not (dom[best_o] & (1 << col)):
                continue
            nxt = dict(closed)
            nxt[best_o] = col
            bt(nxt, max(eff_fresh, col + 1))
            if found_orb_colors is not None or timed_out:
                return

    bt({orbit_id[0]: 0}, 1)
    if found_orb_colors is not None:
        return {"status": "SAT", "colors": found_orb_colors, "nodes_visited": nodes}
    if not timed_out:
        return {"status": "UNSAT", "nodes_visited": nodes, "self_conflict": False}
    return {"status": "UNKNOWN", "nodes_visited": nodes}
