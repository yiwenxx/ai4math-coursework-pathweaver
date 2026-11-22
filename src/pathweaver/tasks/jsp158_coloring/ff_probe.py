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
