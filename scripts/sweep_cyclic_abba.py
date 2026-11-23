"""Systematic SAT/CDCL cyclic ABBA template sweep and non-separable/non-algebraic probe runner.

Executes the two tracks of the JSP-000158 1/4-exponent breakthrough plan:
1. Track 1A & 1B:
   - Sweeps (m, 3) for m in [23, 85] using exact bitset unit-propagation backtracking,
     3|m torsion-triangle symmetry breaking, prime double-radius orbit reduction,
     and subgroup divisor inheritance, verifying emitted UNSAT trees via `certificate.py`.
   - Sweeps (m, 4) for m in [82, 260] (highlighting the m >= 257 threshold entry window)
     across all multiplicative coset quotients (-1 not in H) and antipodal-equivariant
     quotients c(-x) = (c(x) + 2) mod 4, plus bounded full-space exact search.
2. Track 2A, 2B, 2C:
   - Probes z-coupled affine permutations C(y, z) = sigma(z)*y + F(z) and non-affine
     shifted-pole coupled bijections over F_25 and F_49.
   - Probes multiplicative character / cyclotomic coset shears over F_25 and F_49.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pathweaver.tasks.jsp158_coloring.certificate import verify_cyclic_abba_unsat_tree
from pathweaver.tasks.jsp158_coloring.cyclic_sat import (
    count_cyclic_abba_violations,
    solve_cyclic_abba_coset_quotient,
    solve_cyclic_abba_exact,
    solve_cyclic_abba_prime_double_radius,
)
from pathweaver.tasks.jsp158_coloring.ff_probe import (
    QuadraticField,
    probe_coupled_affine_permutation,
    probe_coupled_bijection_table,
    probe_multiplicative_character_shear,
)


def run_r3_sweep(
    m_start: int = 23,
    m_end: int = 85,
    *,
    exact_wall_seconds: float = 3.0,
    exact_max_nodes: int = 120_000,
) -> dict[str, object]:
    """Sweep r = 3 for m in [m_start, m_end]."""
    unsat_moduli: set[int] = {41, 83}  # Inherited verified prime UNSAT certificates
    records: list[dict[str, object]] = []
    sat_templates: list[dict[str, object]] = []
    certified_unsat_count = 0

    for m in range(m_start, m_end + 1):
        # 1. Check if a proper divisor d | m is already proven UNSAT
        unsat_divisors = sorted(d for d in unsat_moduli if d < m and m % d == 0)
        if unsat_divisors:
            d0 = unsat_divisors[0]
            certified_unsat_count += 1
            unsat_moduli.add(m)
            records.append({
                "m": m,
                "r": 3,
                "status": "UNSAT",
                "mechanism": f"subgroup_embedding_from_m{d0}",
                "divisor": d0,
                "crosses_quarter_threshold": False,
            })
            continue

        if m in unsat_moduli:
            certified_unsat_count += 1
            records.append({
                "m": m,
                "r": 3,
                "status": "UNSAT",
                "mechanism": "inherited_full_tree_certificate",
                "crosses_quarter_threshold": False,
            })
            continue

        # 2. First check all multiplicative coset quotients (-1 not in H)
        coset_res = solve_cyclic_abba_coset_quotient(m, 3, min_subgroup_size=2, wall_seconds_per_subgroup=0.5)
        if coset_res["status"] == "SAT":
            colors = coset_res["colors"]
            assert count_cyclic_abba_violations(m, colors) == 0
            rec = {
                "m": m,
                "r": 3,
                "status": "SAT",
                "mechanism": "multiplicative_coset_quotient",
                "used_colors": len(set(colors)),
                "crosses_quarter_threshold": m > len(set(colors)) ** 4,
                "colors": colors,
                "quotient_details": coset_res["quotient_details"],
            }
            records.append(rec)
            sat_templates.append(rec)
            continue

        # 3. Try Stratum & Coset-Generalized Double-Radius Orbit Reduction first for gcd(m, 6) = 1
        dr_res = solve_cyclic_abba_prime_double_radius(
            m,
            3,
            wall_seconds_per_root=max(4.0, exact_wall_seconds),
            max_nodes_per_root=max(300_000, exact_max_nodes),
            emit_tree=False,
        )
        if dr_res is not None and dr_res["status"] in ("SAT", "UNSAT"):
            if dr_res["status"] == "SAT":
                colors = dr_res["colors"]
                assert count_cyclic_abba_violations(m, colors) == 0
                rec = {
                    "m": m,
                    "r": 3,
                    "status": "SAT",
                    "mechanism": "double_radius_orbit_reduction",
                    "used_colors": dr_res["used_colors"],
                    "crosses_quarter_threshold": dr_res["crosses_quarter_threshold"],
                    "nodes_visited": dr_res["nodes_visited"],
                    "elapsed_seconds": dr_res["elapsed_seconds"],
                    "colors": colors,
                }
                records.append(rec)
                sat_templates.append(rec)
                continue
            unsat_moduli.add(m)
            certified_unsat_count += 1
            records.append({
                "m": m,
                "r": 3,
                "status": "UNSAT",
                "mechanism": "double_radius_orbit_reduction",
                "nodes_visited": dr_res["nodes_visited"],
                "elapsed_seconds": dr_res["elapsed_seconds"],
                "coset_quotients_tested": coset_res["tested_quotient_count"],
                "reduction": dr_res.get("reduction"),
            })
            continue

        # 4. Exact full-space symmetry-broken search
        exact_res = solve_cyclic_abba_exact(
            m,
            3,
            wall_seconds=exact_wall_seconds,
            max_nodes=exact_max_nodes,
            emit_tree=True,
        )
        if exact_res["status"] == "SAT":
            colors = exact_res["colors"]
            assert count_cyclic_abba_violations(m, colors) == 0
            rec = {
                "m": m,
                "r": 3,
                "status": "SAT",
                "mechanism": exact_res["symmetry_mode"],
                "used_colors": exact_res["used_colors"],
                "crosses_quarter_threshold": exact_res["crosses_quarter_threshold"],
                "nodes_visited": exact_res["nodes_visited"],
                "elapsed_seconds": exact_res["elapsed_seconds"],
                "colors": colors,
            }
            records.append(rec)
            sat_templates.append(rec)
            continue

        if exact_res["status"] == "UNSAT":
            cert = exact_res["certificate"]
            ver = verify_cyclic_abba_unsat_tree(cert, max_nodes=max(250_000, exact_max_nodes * 4))
            assert ver["status"] == "verified"
            unsat_moduli.add(m)
            certified_unsat_count += 1
            records.append({
                "m": m,
                "r": 3,
                "status": "UNSAT",
                "mechanism": exact_res["symmetry_mode"],
                "nodes_visited": exact_res["nodes_visited"],
                "verified_tree_nodes": ver["verified_nodes"],
                "elapsed_seconds": exact_res["elapsed_seconds"],
                "coset_quotients_tested": coset_res["tested_quotient_count"],
                "certificate_verified": True,
            })
            continue

        records.append({
            "m": m,
            "r": 3,
            "status": "FRONTIER_OPEN_AT_BUDGET",
            "coset_quotient_status": coset_res["status"],
            "coset_quotients_tested": coset_res["tested_quotient_count"],
            "exact_nodes_visited": exact_res["nodes_visited"],
            "double_radius_applicable": dr_res is not None,
        })

    return {
        "palette_limit": 3,
        "range": [m_start, m_end],
        "total_moduli": m_end - m_start + 1,
        "sat_count": len(sat_templates),
        "certified_unsat_count": certified_unsat_count,
        "sat_moduli": [r["m"] for r in sat_templates],
        "unsat_moduli": sorted(m for m in unsat_moduli if m_start <= m <= m_end),
        "crosses_quarter_threshold_found": any(r["crosses_quarter_threshold"] for r in sat_templates),
        "records": records,
    }


def run_r4_sweep(
    m_start: int = 82,
    m_end: int = 260,
    *,
    min_subgroup_size: int = 3,
) -> dict[str, object]:
    """Sweep r = 4 for m in [m_start, m_end] via multiplicative coset and antipodal-equivariant quotients."""
    records: list[dict[str, object]] = []
    sat_templates: list[dict[str, object]] = []
    quotient_unsat_moduli: list[int] = []
    total_quotients_checked = 0

    for m in range(m_start, m_end + 1):
        # For threshold window m in [257, 260], check all subgroups of size >= 2; for [82, 256], size >= min_subgroup_size
        sub_min = 2 if m >= 257 else min_subgroup_size
        max_orb = 135 if m >= 257 else 65
        coset_res = solve_cyclic_abba_coset_quotient(
            m,
            4,
            min_subgroup_size=sub_min,
            max_orbits=max_orb,
            wall_seconds_per_subgroup=0.4 if m < 257 else 1.5,
        )
        total_quotients_checked += coset_res["tested_quotient_count"]

        if coset_res["status"] == "SAT":
            colors = coset_res["colors"]
            assert count_cyclic_abba_violations(m, colors) == 0
            rec = {
                "m": m,
                "r": 4,
                "status": "SAT",
                "mechanism": coset_res["quotient_details"]["kind"],
                "used_colors": len(set(colors)),
                "crosses_quarter_threshold": m > len(set(colors)) ** 4,
                "quotient_details": coset_res["quotient_details"],
                "colors": colors,
            }
            records.append(rec)
            sat_templates.append(rec)
        else:
            if coset_res["status"] == "UNSAT":
                quotient_unsat_moduli.append(m)
            if m >= 255 or m <= 90 or coset_res["status"] == "SAT":
                records.append({
                    "m": m,
                    "r": 4,
                    "status": f"COSET_{coset_res['status']}",
                    "tested_quotient_count": coset_res["tested_quotient_count"],
                    "tested_quotients": coset_res["tested_quotients"][:6],
                })

    return {
        "palette_limit": 4,
        "range": [m_start, m_end],
        "total_moduli": m_end - m_start + 1,
        "total_quotients_checked": total_quotients_checked,
        "sat_count": len(sat_templates),
        "sat_moduli": [r["m"] for r in sat_templates],
        "quotient_unsat_moduli_count": len(quotient_unsat_moduli),
        "threshold_window_257_260": [r for r in records if int(r["m"]) >= 257],
        "crosses_quarter_threshold_found": any(r["crosses_quarter_threshold"] for r in sat_templates),
        "highlighted_records": records,
    }


def run_theoretical_probes() -> dict[str, object]:
    """Run Track 2 finite-field probes via ff_probe.py."""
    f25 = QuadraticField.build(5)
    f49 = QuadraticField.build(7)

    # 2A-1: Coupled affine permutation with Frobenius + trace scaling sigma(z) = z^p + 2*z + gamma
    # (choosing root-free sigma(z) = Tr(z) + w where w not in F_p)
    w25 = f25.elem(1, 0)
    sigma_trace_shift = lambda f, z: f.add[f.trace[z]][w25]
    # Even when F(z) is the Nov19-005 trace-denominator rational shear (which is ABBA-free for uncoupled pi),
    # coupling sigma(z) via C(y, z) = sigma(z)*y + F(z) triggers D_sigma != 0 and immediately creates ABBA!
    num_005 = [f25.elem(1, 0), 0, 0, 1]  # z^3 + w (irreducible cubic over F_25)
    f_005_fn = lambda f, z: f.mul[f.eval_poly(num_005, z)][f.inv[sigma_trace_shift(f, z)]]
    coupled_affine_005 = probe_coupled_affine_permutation(f25, sigma_trace_shift, f_005_fn)

    # 2A-2: Coupled affine permutation with quadratic norm scaling sigma(z) = z^(p+1) + w in F_25*
    # Check z^(5+1) = z^6 in F_25: since 6 | 24, z^6 lies in F_5, so z^6 + w is always in F_5 + w (never 0!).
    sigma_norm_shift = lambda f, z: f.add[f.mul[z][f.frob[z]]][w25]
    coupled_affine_norm = probe_coupled_affine_permutation(f25, sigma_norm_shift, f_005_fn)

    # 2A-3: Non-affine shifted-pole inversion coupling pi_z(y) = (y + z)^(-1) + F(z)
    # where 0^(-1) := 0, which is a true bijection y -> (y + alpha(z))^(-1) + beta(z) on F_25!
    pi_table_inversion: list[list[int]] = []
    for z in range(f25.q):
        fz = f_005_fn(f25, z)
        row = [f25.add[f25.inv[f25.add[y][z]]][fz] for y in range(f25.q)]
        pi_table_inversion.append(row)
    non_affine_inversion_res = probe_coupled_bijection_table(f25, pi_table_inversion)

    # 2B: Multiplicative character / cyclotomic coset shear f(z) = chi_k(z) * z^3 over F_25 and F_49
    # Over F_25 (q-1 = 24): test order-2 quadratic character (weights [1, w]) and order-3 cubic character ([1, w, w+1])
    mult_char_f25_deg2 = probe_multiplicative_character_shear(f25, 2, [1, w25])
    mult_char_f25_deg3 = probe_multiplicative_character_shear(f25, 3, [1, w25, f25.elem(1, 1)])
    w49 = f49.elem(1, 0)
    mult_char_f49_deg2 = probe_multiplicative_character_shear(f49, 2, [1, w49])

    return {
        "coupled_affine_on_005_trace_shear_f25": coupled_affine_005,
        "coupled_affine_norm_scaling_on_005_f25": coupled_affine_norm,
        "non_affine_shifted_pole_bijection_f25": non_affine_inversion_res,
        "multiplicative_character_shear_f25_mod2": mult_char_f25_deg2,
        "multiplicative_character_shear_f25_mod3": mult_char_f25_deg3,
        "multiplicative_character_shear_f49_mod2": mult_char_f49_deg2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/jsp158_quarter_breakthrough_sweep.json",
    )
    parser.add_argument("--r3-wall-seconds", type=float, default=4.0)
    parser.add_argument("--r3-max-nodes", type=int, default=120_000)
    args = parser.parse_args()

    t0 = time.monotonic()
    r3_summary = run_r3_sweep(
        23, 85,
        exact_wall_seconds=args.r3_wall_seconds,
        exact_max_nodes=args.r3_max_nodes,
    )
    r4_summary = run_r4_sweep(82, 260, min_subgroup_size=3)
    probes = run_theoretical_probes()

    payload = {
        "schema_version": 1,
        "problem": "JSP-000158 / Erdos problem 160 — 1/4 Exponent Breakthrough Sweep & Theoretical Probes",
        "elapsed_seconds": round(time.monotonic() - t0, 3),
        "track1_cyclic_r3_sweep": r3_summary,
        "track1_cyclic_r4_sweep": r4_summary,
        "track2_theoretical_probes": probes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "elapsed_seconds": payload["elapsed_seconds"],
        "r3_sat_moduli": r3_summary["sat_moduli"],
        "r3_certified_unsat_count": r3_summary["certified_unsat_count"],
        "r4_sat_moduli": r4_summary["sat_moduli"],
        "r4_total_quotients_checked": r4_summary["total_quotients_checked"],
        "r4_quotient_unsat_count": r4_summary["quotient_unsat_moduli_count"],
        "track2_coupled_affine_has_abba": probes["coupled_affine_on_005_trace_shear_f25"]["has_abba"],
        "track2_non_affine_pole_has_abba": probes["non_affine_shifted_pole_bijection_f25"]["has_abba"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
