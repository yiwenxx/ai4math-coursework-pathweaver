"""Small finite-field exact arithmetic and automatic counterexample probe for JSP-000158.

Targets quadratic extensions F_{p^2} = F_p[w] / (w^2 - eta) (e.g., F_25, F_49, F_121)
using pure Python standard library so candidate algebraic claims can be falsified in
milliseconds before spending long reasoning calls.
"""
from dataclasses import dataclass
from typing import Callable


def _find_non_residue(p: int) -> int:
    for eta in range(2, p):
        if pow(eta, (p - 1) // 2, p) == p - 1:
            return eta
    raise ValueError(f"No quadratic non-residue found for prime p={p}")


@dataclass
class QuadraticField:
    """Exact arithmetic tables for F_{p^2} = F_p[w] / (w^2 - eta).

    Element index i = u * p + v represents u*w + v with u, v in 0..p-1.
    """
    p: int
    eta: int
    q: int
    add: list[list[int]]
    sub: list[list[int]]
    mul: list[list[int]]
    inv: list[int]
    frob: list[int]  # x -> x^p
    trace: list[int]  # x + x^p (as element index in F_p subset 0..p-1)
    cube: list[int]

    @classmethod
    def build(cls, p: int, eta: int | None = None) -> "QuadraticField":
        if type(p) is not int or p < 3 or any(p % d == 0 for d in range(2, int(p**0.5) + 1)):
            raise ValueError(f"p must be an odd prime, got {p!r}")
        if eta is None:
            eta = _find_non_residue(p)
        elif pow(eta % p, (p - 1) // 2, p) != p - 1:
            raise ValueError(f"eta={eta} is not a quadratic non-residue mod {p}")
        q = p * p
        u_tab = [i // p for i in range(q)]
        v_tab = [i % p for i in range(q)]

        add = [[((u_tab[i] + u_tab[j]) % p) * p + ((v_tab[i] + v_tab[j]) % p) for j in range(q)] for i in range(q)]
        sub = [[((u_tab[i] - u_tab[j]) % p) * p + ((v_tab[i] - v_tab[j]) % p) for j in range(q)] for i in range(q)]
        mul = [
            [
                ((u_tab[i] * v_tab[j] + v_tab[i] * u_tab[j]) % p) * p
                + ((v_tab[i] * v_tab[j] + eta * u_tab[i] * u_tab[j]) % p)
                for j in range(q)
            ]
            for i in range(q)
        ]
        inv = [0] * q
        for i in range(1, q):
            for j in range(1, q):
                if mul[i][j] == 1:
                    inv[i] = j
                    break
        # w^p = w * (w^2)^((p-1)/2) = -w, so (u*w + v)^p = (-u mod p)*w + v.
        frob = [((-u_tab[i]) % p) * p + v_tab[i] for i in range(q)]
        trace = [add[i][frob[i]] for i in range(q)]
        cube = [mul[mul[i][i]][i] for i in range(q)]
        return cls(p=p, eta=eta, q=q, add=add, sub=sub, mul=mul, inv=inv, frob=frob, trace=trace, cube=cube)

    def elem(self, u: int, v: int) -> int:
        return (u % self.p) * self.p + (v % self.p)

    def coords(self, idx: int) -> tuple[int, int]:
        return idx // self.p, idx % self.p

    def eval_poly(self, coeffs: list[int], x: int) -> int:
        """Evaluate sum coeffs[k] * x^k (low-to-high)."""
        acc = 0
        for c in reversed(coeffs):
            acc = self.add[self.mul[acc][x]][c]
        return acc

    def pow_elem(self, x: int, exp: int) -> int:
        acc = 1
        base = x
        e = exp
        while e > 0:
            if e & 1:
                acc = self.mul[acc][base]
            base = self.mul[base][base]
            e >>= 1
        return acc


def probe_third_difference_zero(
    field: QuadraticField,
    fn: Callable[[QuadraticField, int], int],
) -> dict[str, object]:
    """Exhaustively test whether a function f: F_q -> F_q has any nonzero-step 3rd-diff zero.

    Returns the first witness (z0, h) with h != 0 and
    f(z0 + 3h) - 3 f(z0 + 2h) + 3 f(z0 + h) - f(z0) == 0, or confirms none exists.
    Directly tests pure-shear ABBA / third-difference claims over small F_{p^2}.
    """
    q = field.q
    vals = [fn(field, z) for z in range(q)]
    add, sub, mul = field.add, field.sub, field.mul
    three = 3 % field.p
    for h in range(1, q):
        h2 = add[h][h]
        h3 = add[h2][h]
        for z0 in range(q):
            y0 = vals[z0]
            y1 = vals[add[z0][h]]
            y2 = vals[add[z0][h2]]
            y3 = vals[add[z0][h3]]
            # delta3 = (y3 - y0) - 3 * (y2 - y1)
            d3 = sub[sub[y3][y0]][mul[three][sub[y2][y1]]]
            if d3 == 0:
                return {
                    "field": f"F_{q}",
                    "has_zero_third_difference": True,
                    "witness": {
                        "z0": field.coords(z0),
                        "h": field.coords(h),
                        "values": [field.coords(y0), field.coords(y1), field.coords(y2), field.coords(y3)],
                    },
                }
    return {"field": f"F_{q}", "has_zero_third_difference": False, "witness": None}


def probe_rational_shear(
    p: int,
    num_coeffs: list[int],
    den_fn: Callable[[QuadraticField, int], int],
    eta: int | None = None,
) -> dict[str, object]:
    """Test f(z) = A(z) / B(z) over F_{p^2} after checking B is root-free."""
    field = QuadraticField.build(p, eta=eta)
    for z in range(field.q):
        if den_fn(field, z) == 0:
            raise ValueError(f"Denominator vanishes at {field.coords(z)} in F_{field.q}")

    def ratio(f: QuadraticField, z: int) -> int:
        return f.mul[f.eval_poly(num_coeffs, z)][f.inv[den_fn(f, z)]]

    result = probe_third_difference_zero(field, ratio)
    result["root_free_verified"] = True
    return result


def probe_coupled_affine_permutation(
    field: QuadraticField,
    sigma_fn: Callable[[QuadraticField, int], int],
    f_fn: Callable[[QuadraticField, int], int],
) -> dict[str, object]:
    """Exhaustively test z-coupled affine permutation C(y, z) = sigma(z) * y + F(z) over F_q x F_q.

    Along z_i = z0 + i*h (h != 0) and y_i = y0 + i*eta, ABBA (C_0 == C_3 and C_1 == C_2) is a
    2x2 linear system for (y0, eta) with determinant:
        D_sigma(z0, h) = (s3 - s0)*(2*s2 - s1) - 3*s3*(s2 - s1).
    Whenever D_sigma(z0, h) != 0, Cramer's rule yields a unique ABBA witness (y0, eta) regardless
    of F(z) (even if F is non-polynomial).
    """
    q = field.q
    add, sub, mul, inv = field.add, field.sub, field.mul, field.inv
    two = 2 % field.p
    three = 3 % field.p

    sigmas = [sigma_fn(field, z) for z in range(q)]
    if any(s == 0 for s in sigmas):
        raise ValueError("sigma(z) must be nonzero on F_q for y -> sigma(z)*y + F(z) to be a bijection")
    f_vals = [f_fn(field, z) for z in range(q)]

    total_pairs = 0
    nonzero_det_pairs = 0
    first_det_witness: dict[str, object] | None = None
    first_degenerate_witness: dict[str, object] | None = None

    for h in range(1, q):
        h2 = add[h][h]
        h3 = add[h2][h]
        for z0 in range(q):
            total_pairs += 1
            z1 = add[z0][h]
            z2 = add[z0][h2]
            z3 = add[z0][h3]

            s0, s1, s2, s3 = sigmas[z0], sigmas[z1], sigmas[z2], sigmas[z3]
            f0, f1, f2, f3 = f_vals[z0], f_vals[z1], f_vals[z2], f_vals[z3]

            s3_m_s0 = sub[s3][s0]
            two_s2_m_s1 = sub[mul[two][s2]][s1]
            three_s3 = mul[three][s3]
            s2_m_s1 = sub[s2][s1]

            # D = (s3 - s0)*(2*s2 - s1) - 3*s3*(s2 - s1)
            det = sub[mul[s3_m_s0][two_s2_m_s1]][mul[three_s3][s2_m_s1]]
            if det != 0:
                nonzero_det_pairs += 1
                if first_det_witness is None:
                    inv_det = inv[det]
                    # Y0 = (f0 - f3)*(2*s2 - s1) + 3*s3*(f2 - f1)
                    y0_num = add[mul[sub[f0][f3]][two_s2_m_s1]][mul[three_s3][sub[f2][f1]]]
                    # H = (s0 - s3)*(f2 - f1) + (s2 - s1)*(f3 - f0)
                    eta_num = add[mul[sub[s0][s3]][sub[f2][f1]]][mul[s2_m_s1][sub[f3][f0]]]
                    y0 = mul[y0_num][inv_det]
                    eta = mul[eta_num][inv_det]

                    c_vals = [
                        add[mul[sigmas[z_i]][add[y0][mul[i % field.p][eta]]]][f_vals[z_i]]
                        for i, z_i in enumerate((z0, z1, z2, z3))
                    ]
                    if not (c_vals[0] == c_vals[3] and c_vals[1] == c_vals[2]):
                        raise RuntimeError("Cramer determinant witness failed independent ABBA check")
                    first_det_witness = {
                        "z0": field.coords(z0),
                        "h": field.coords(h),
                        "y0": field.coords(y0),
                        "eta": field.coords(eta),
                        "det": field.coords(det),
                        "colors": [field.coords(c) for c in c_vals],
                    }
            elif first_degenerate_witness is None:
                # Check if singular system still admits a solution (y0, eta)
                rhs1 = sub[f0][f3]
                rhs2 = sub[f1][f2]
                for y0 in range(q):
                    lhs1_base = mul[s3_m_s0][y0]
                    lhs2_base = mul[s2_m_s1][y0]
                    found = False
                    for eta in range(q):
                        if (
                            add[lhs1_base][mul[three_s3][eta]] == rhs1
                            and add[lhs2_base][mul[two_s2_m_s1][eta]] == rhs2
                        ):
                            first_degenerate_witness = {
                                "z0": field.coords(z0),
                                "h": field.coords(h),
                                "y0": field.coords(y0),
                                "eta": field.coords(eta),
                            }
                            found = True
                            break
                    if found:
                        break

    has_abba = (first_det_witness is not None) or (first_degenerate_witness is not None)
    return {
        "field": f"F_{q}",
        "total_z_progressions": total_pairs,
        "nonzero_det_progressions": nonzero_det_pairs,
        "nonzero_det_ratio": round(nonzero_det_pairs / total_pairs, 6),
        "has_abba": has_abba,
        "cramer_witness": first_det_witness,
        "degenerate_witness": first_degenerate_witness,
    }


def probe_coupled_bijection_table(
    field: QuadraticField,
    pi_table: list[list[int]],
) -> dict[str, object]:
    """Exhaustively test any general coupled coloring C(y, z) = pi_table[z][y] on F_q x F_q.

    Covers non-affine coupled permutations (such as shifted-pole inversions
    pi_z(y) = (y + alpha(z))^(-1) + F(z) or multiplicative coset permutations).
    """
    q = field.q
    add = field.add
    if len(pi_table) != q or any(len(row) != q for row in pi_table):
        raise ValueError(f"pi_table must be a {q}x{q} array")

    for h in range(1, q):
        h2 = add[h][h]
        h3 = add[h2][h]
        for z0 in range(q):
            r0 = pi_table[z0]
            r1 = pi_table[add[z0][h]]
            r2 = pi_table[add[z0][h2]]
            r3 = pi_table[add[z0][h3]]
            for eta in range(q):
                e2 = add[eta][eta]
                e3 = add[e2][eta]
                for y0 in range(q):
                    c0 = r0[y0]
                    c3 = r3[add[y0][e3]]
                    if c0 == c3:
                        c1 = r1[add[y0][eta]]
                        c2 = r2[add[y0][e2]]
                        if c1 == c2:
                            return {
                                "field": f"F_{q}",
                                "has_abba": True,
                                "witness": {
                                    "y0": field.coords(y0),
                                    "eta": field.coords(eta),
                                    "z0": field.coords(z0),
                                    "h": field.coords(h),
                                    "colors": [c0, c1, c2, c3],
                                },
                            }
    return {"field": f"F_{q}", "has_abba": False, "witness": None}


def probe_multiplicative_character_shear(
    field: QuadraticField,
    coset_modulus: int,
    coset_weights: list[int],
    poly_coeffs: list[int] | None = None,
) -> dict[str, object]:
    """Test non-polynomial multiplicative character / cyclotomic coset shear f(z) over F_{p^2}.

    Maps each nonzero z in F_q* to its cyclotomic coset index (dlog(z) mod coset_modulus),
    multiplies/shifts by `coset_weights[idx]`, and optionally adds a base polynomial.
    Tests whether any nonzero step h gives a zero third difference delta^3 f(z0, h) == 0.
    """
    q = field.q
    if (q - 1) % coset_modulus != 0 or len(coset_weights) != coset_modulus:
        raise ValueError(f"coset_modulus={coset_modulus} must divide q-1={q - 1} and match coset_weights length")

    # Find a primitive root g of F_q*
    g = 1
    for cand in range(2, q):
        seen = set()
        cur = 1
        for _ in range(q - 1):
            seen.add(cur)
            cur = field.mul[cur][cand]
        if len(seen) == q - 1:
            g = cand
            break

    dlog = [0] * q
    cur = 1
    for exp in range(q - 1):
        dlog[cur] = exp
        cur = field.mul[cur][g]

    def fn(f: QuadraticField, z: int) -> int:
        base = f.eval_poly(poly_coeffs, z) if poly_coeffs else 0
        if z == 0:
            return base
        c_weight = coset_weights[dlog[z] % coset_modulus]
        # Non-algebraic piecewise scaling: c_weight * z^3 + base
        return f.add[base][f.mul[c_weight][f.cube[z]]]

    res = probe_third_difference_zero(field, fn)
    res["primitive_root"] = field.coords(g)
    res["coset_modulus"] = coset_modulus
    return res

