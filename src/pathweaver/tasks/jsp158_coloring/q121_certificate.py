"""Independent generator and zero-trust verifier for the q=121 mixed-curve certificate.

Mathematical statement certified over F_121 = F_11[w] / (w^2 - 2):
For every depressed irreducible binary cubic norm form H(a,c) = a^3 + P*a*c^2 + Q*c^3
(all 4,880 irreducible cubics X^3 + P*X + Q over F_121, partitioned into 42 scaling
orbits under (P,Q) -> (P*r^2, Q*r^3)), every nonzero k in F_121* (8 cosets of 8th powers
under (a,c) = t*(A,C)), every l in F_121 (121 values), and every target n in F_121:
there exists (a, c) in F_121^2 such that
    H(a, c) + k * c^11 + l * c == n   AND   J(a, c) = 3*a^2 + P*c^2 != 0.

The generator emits a compact JSON certificate listing the canonical representatives and
an explicit small set of c-values per (rep, k_rep, l) group. The independent verifier
rebuilds F_121 from scratch, verifies complete coverage of all 4,880 irreducible cubics and
all 120 nonzero k's under the scaling symmetries, and checks that the listed c-values yield
a valid (a, c) with J(a, c) != 0 for every single one of the 40,656 * 121 = 4,919,376 pairs.
"""
import json
from pathlib import Path
from typing import Any

from pathweaver.core.contracts import digest
from .ff_probe import QuadraticField

SCHEMA_VERSION = 1
P = 11
ETA = 2  # 2^5 = 32 == -1 (mod 11), so w^2 - 2 is irreducible over F_11.
Q = 121


def _depressed_irreducibles(field: QuadraticField) -> list[tuple[int, int]]:
    """Return all (P, Q) in F_121^2 such that X^3 + P*X + Q has no root in F_121."""
    add, mul, cube = field.add, field.mul, field.cube
    irreducibles: list[tuple[int, int]] = []
    for p_coeff in range(Q):
        # X^3 + P*X + Q has a root iff -Q is in the image of X -> X^3 + P*X.
        image = {add[cube[x]][mul[p_coeff][x]] for x in range(Q)}
        for q_coeff in range(Q):
            neg_q = field.sub[0][q_coeff]
            if neg_q not in image:
                irreducibles.append((p_coeff, q_coeff))
    return irreducibles


def _canonical_orbit_reps(field: QuadraticField) -> tuple[list[tuple[int, int]], list[int], int]:
    """Compute canonical representatives for the 42 cubic orbits and 8 k-cosets."""
    mul = field.mul
    irreducibles = _depressed_irreducibles(field)
    irred_set = set(irreducibles)
    seen: set[tuple[int, int]] = set()
    cubic_reps: list[tuple[int, int]] = []
    for pair in irreducibles:
        if pair in seen:
            continue
        p0, q0 = pair
        orbit = set()
        for r in range(1, Q):
            r2 = mul[r][r]
            r3 = mul[r2][r]
            orbit.add((mul[p0][r2], mul[q0][r3]))
        if not orbit.issubset(irred_set):
            raise ValueError("Scaling orbit escaped irreducible set")
        seen.update(orbit)
        cubic_reps.append(min(orbit))

    eighth_powers = {field.pow_elem(t, 8) for t in range(1, Q)}
    seen_k: set[int] = set()
    k_reps: list[int] = []
    for k in range(1, Q):
        if k in seen_k:
            continue
        coset = {mul[k][e] for e in eighth_powers}
        seen_k.update(coset)
        k_reps.append(min(coset))
    return cubic_reps, k_reps, len(irreducibles)


def generate_certificate() -> dict[str, Any]:
    """Generate a compact, independently checkable witness certificate for all 40,656 groups."""
    field = QuadraticField.build(P, eta=ETA)
    add, mul, frob, cube = field.add, field.mul, field.frob, field.cube
    cubic_reps, k_reps, irred_count = _canonical_orbit_reps(field)
    if irred_count != 4880 or len(cubic_reps) != 42 or len(k_reps) != 8:
        raise ValueError(f"Unexpected orbit counts: {irred_count}, {len(cubic_reps)}, {len(k_reps)}")

    three_a2 = [mul[3][mul[a][a]] for a in range(Q)]
    c2_tab = [mul[c][c] for c in range(Q)]
    c3_tab = [cube[c] for c in range(Q)]
    cfrob_tab = [frob[c] for c in range(Q)]
    full_mask = (1 << Q) - 1

    # For each (rep_idx, k_idx, l_idx), store the minimal greedy list of c-values covering all 121 n's.
    cover_witnesses: list[list[int]] = []
    max_cover_len = 0
    total_c_checks = 0

    for p_coeff, q_coeff in cubic_reps:
        # Precompute for each c: bitmask of distinct H(a,c) values attained with J(a,c) != 0.
        # Notice H(a,c) + shift depends on (k,l) only by an additive shift in F_121!
        # Wait: F_121 addition is NOT cyclic shift on indices, so store tuple of attained H values per c.
        h_values_per_c: list[tuple[int, ...]] = []
        for c in range(Q):
            pc2 = mul[p_coeff][c2_tab[c]]
            qc3 = mul[q_coeff][c3_tab[c]]
            vals = set()
            for a in range(Q):
                if add[three_a2[a]][pc2] != 0:
                    h_val = add[add[cube[a]][mul[pc2][a]]][qc3]
                    vals.add(h_val)
            h_values_per_c.append(tuple(vals))

        # Order c by largest distinct H-image size first for tiny covering sets.
        c_order = sorted(range(Q), key=lambda c: (-len(h_values_per_c[c]), c))

        for k_val in k_reps:
            kc11 = [mul[k_val][cfrob_tab[c]] for c in range(Q)]
            for l_val in range(Q):
                covered = 0
                chosen: list[int] = []
                for c in c_order:
                    shift = add[kc11[c]][mul[l_val][c]]
                    add_shift = add[shift]
                    new_bits = 0
                    for hv in h_values_per_c[c]:
                        new_bits |= 1 << add_shift[hv]
                    if new_bits & ~covered:
                        covered |= new_bits
                        chosen.append(c)
                        if covered == full_mask:
                            break
                if covered != full_mask:
                    raise RuntimeError(f"Uncovered target for P={p_coeff}, Q={q_coeff}, k={k_val}, l={l_val}")
                cover_witnesses.append(chosen)
                if len(chosen) > max_cover_len:
                    max_cover_len = len(chosen)
                total_c_checks += len(chosen)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "problem": "jsp158_q121_mixed_frobenius_cubic_norm_curve",
        "field": {"p": P, "e": 2, "q": Q, "modulus": "w^2 - 2", "element_encoding": "idx = u*11 + v for u*w + v"},
        "counts": {
            "depressed_irreducible_cubics": irred_count,
            "cubic_orbit_representatives": len(cubic_reps),
            "k_eighth_power_cosets": len(k_reps),
            "linear_coefficients": Q,
            "normalized_groups": len(cover_witnesses),
            "total_equations_certified": len(cover_witnesses) * Q,
            "max_c_witnesses_per_group": max_cover_len,
            "mean_c_witnesses_per_group": round(total_c_checks / len(cover_witnesses), 4),
        },
        "cubic_representatives": [[p_c, q_c] for p_c, q_c in cubic_reps],
        "k_representatives": k_reps,
        "group_order": "for rep_idx in range(42): for k_idx in range(8): for l_val in range(121)",
        "c_witnesses": cover_witnesses,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload["payload_sha256"] = digest(canonical)
    return payload


def verify_certificate(cert: dict[str, Any]) -> dict[str, Any]:
    """Independently verify orbit completeness and every single one of the 4,919,376 equations.

    Never trusts any precomputed count or orbit claim in the certificate.
    """
    if not isinstance(cert, dict) or cert.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported or malformed q=121 certificate")
    expected_sha = cert.get("payload_sha256")
    if isinstance(expected_sha, str):
        stripped = {k: v for k, v in cert.items() if k != "payload_sha256"}
        actual_sha = digest(json.dumps(stripped, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        if actual_sha != expected_sha:
            raise ValueError("Certificate payload_sha256 mismatch")

    field = QuadraticField.build(P, eta=ETA)
    add, mul, frob, cube = field.add, field.mul, field.frob, field.cube

    # 1. Independently verify the supplied cubic_representatives cover ALL 4,880 depressed irreducibles.
    cubic_reps = [(int(pair[0]), int(pair[1])) for pair in cert["cubic_representatives"]]
    all_irred = set(_depressed_irreducibles(field))
    if len(all_irred) != 4880:
        raise ValueError(f"Expected 4880 depressed irreducibles over F_121, got {len(all_irred)}")
    covered_irred: set[tuple[int, int]] = set()
    for p0, q0 in cubic_reps:
        if (p0, q0) not in all_irred:
            raise ValueError(f"Representative ({p0}, {q0}) is not an irreducible depressed cubic")
        for r in range(1, Q):
            r2 = mul[r][r]
            r3 = mul[r2][r]
            covered_irred.add((mul[p0][r2], mul[q0][r3]))
    if covered_irred != all_irred:
        raise ValueError(f"Cubic representatives cover {len(covered_irred)} / {len(all_irred)} irreducibles")

    # 2. Independently verify the supplied k_representatives cover ALL 120 nonzero elements under 8th-power scaling.
    k_reps = [int(k) for k in cert["k_representatives"]]
    eighth_powers = {field.pow_elem(t, 8) for t in range(1, Q)}
    covered_k: set[int] = set()
    for k0 in k_reps:
        if not 1 <= k0 < Q:
            raise ValueError(f"Invalid nonzero k representative: {k0}")
        for e in eighth_powers:
            covered_k.add(mul[k0][e])
    if len(covered_k) != Q - 1:
        raise ValueError(f"k representatives cover {len(covered_k)} / {Q - 1} nonzero elements")

    # 3. Verify every (rep, k_rep, l) group covers all 121 targets n with J(a,c) = 3a^2 + Pc^2 != 0
    # using ONLY the explicit c values listed in the certificate.
    c_witnesses = cert["c_witnesses"]
    expected_groups = len(cubic_reps) * len(k_reps) * Q
    if len(c_witnesses) != expected_groups:
        raise ValueError(f"Expected {expected_groups} witness lists, got {len(c_witnesses)}")

    three_a2 = [mul[3][mul[a][a]] for a in range(Q)]
    c2_tab = [mul[c][c] for c in range(Q)]
    c3_tab = [cube[c] for c in range(Q)]
    cfrob_tab = [frob[c] for c in range(Q)]
    full_mask = (1 << Q) - 1

    group_idx = 0
    total_equations = 0
    for p_coeff, q_coeff in cubic_reps:
        for k_val in k_reps:
            for l_val in range(Q):
                chosen_cs = c_witnesses[group_idx]
                group_idx += 1
                if not isinstance(chosen_cs, list) or not chosen_cs:
                    raise ValueError(f"Empty c_witness list at group {group_idx - 1}")
                covered = 0
                for c in chosen_cs:
                    if type(c) is not int or not 0 <= c < Q:
                        raise ValueError(f"Invalid c={c!r} at group {group_idx - 1}")
                    pc2 = mul[p_coeff][c2_tab[c]]
                    tail = add[add[mul[q_coeff][c3_tab[c]]][mul[k_val][cfrob_tab[c]]]][mul[l_val][c]]
                    for a in range(Q):
                        if add[three_a2[a]][pc2] != 0:
                            val = add[add[cube[a]][mul[pc2][a]]][tail]
                            covered |= 1 << val
                if covered != full_mask:
                    raise ValueError(
                        f"Group {group_idx - 1} (P={p_coeff}, Q={q_coeff}, k={k_val}, l={l_val}) failed full coverage"
                    )
                total_equations += Q

    return {
        "status": "verified",
        "evidence": "finite_optimal_certificate",
        "field": "F_121",
        "depressed_irreducible_cubics_verified": len(covered_irred),
        "nonzero_k_verified": len(covered_k),
        "normalized_groups_verified": group_idx,
        "total_equations_verified": total_equations,
        "payload_sha256": cert.get("payload_sha256"),
    }


def save_certificate(path: str | Path, cert: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cert, separators=(",", ":")) + "\n", encoding="utf-8")


def load_certificate(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
