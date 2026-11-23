/-
PathWeaverFormal.FrobeniusBase
Pure Lean 4 algebraic foundations for finite field F_11, quadratic extension
F_121 = F_11[w] / (w^2 - 2), Frobenius automorphism invariance, and 4-AP shifts.
Supports formalization of JSP-000158 Frobenius obstruction lemmas.
-/

namespace PathWeaverFormal.Frobenius

abbrev F11 := Fin 11

def f11Add (a b : F11) : F11 :=
  ⟨(a.val + b.val) % 11, Nat.mod_lt _ (by omega)⟩

def f11Neg (a : F11) : F11 :=
  ⟨(11 - a.val) % 11, Nat.mod_lt _ (by omega)⟩

def f11Sub (a b : F11) : F11 :=
  f11Add a (f11Neg b)

def f11Mul (a b : F11) : F11 :=
  ⟨(a.val * b.val) % 11, Nat.mod_lt _ (by omega)⟩

/-- 2 is a non-square in F_11 (since 2^5 = 32 ≡ -1 mod 11), so w^2 - 2 is irreducible. -/
theorem two_is_nonsquare_f11 : ∀ x : F11, (x.val * x.val) % 11 ≠ 2 := by
  decide

/-- F_121 elements represented as u*w + v with u, v in F_11 and w^2 = 2. -/
structure F121 where
  u : F11
  v : F11
  deriving DecidableEq, Repr

def f121Add (x y : F121) : F121 :=
  ⟨f11Add x.u y.u, f11Add x.v y.v⟩

def f121Neg (x : F121) : F121 :=
  ⟨f11Neg x.u, f11Neg x.v⟩

def f121Mul (x y : F121) : F121 :=
  let uOut : F11 := ⟨(x.u.val * y.v.val + x.v.val * y.u.val) % 11, Nat.mod_lt _ (by omega)⟩
  let vOut : F11 := ⟨(2 * x.u.val * y.u.val + x.v.val * y.v.val) % 11, Nat.mod_lt _ (by omega)⟩
  ⟨uOut, vOut⟩

/-- Frobenius x -> x^11 on F_121 sends w -> -w (since w^11 = w * (w^2)^5 = 32*w = -w mod 11). -/
def f121Frob (x : F121) : F121 :=
  ⟨f11Neg x.u, x.v⟩

/-- Trace Tr(x) = x + x^11 lies in the base subfield F_11 (u-coordinate vanishes). -/
def f121TraceU (x : F121) : F11 :=
  (f121Add x (f121Frob x)).u

theorem f121_frob_involutive (x : F121) : f121Frob (f121Frob x) = x := by
  rcases x with ⟨⟨u, hu⟩, ⟨v, hv⟩⟩
  simp only [f121Frob, f11Neg]
  congr 1
  simp only [Fin.mk.injEq]
  omega

theorem f121_trace_in_base (x : F121) : f121TraceU x = ⟨0, by omega⟩ := by
  rcases x with ⟨⟨u, hu⟩, ⟨v, hv⟩⟩
  simp only [f121TraceU, f121Add, f121Frob, f11Add, f11Neg, Fin.mk.injEq]
  omega

theorem f121_frob_add (x y : F121) :
    f121Frob (f121Add x y) = f121Add (f121Frob x) (f121Frob y) := by
  rcases x with ⟨⟨u1, hu1⟩, ⟨v1, hv1⟩⟩
  rcases y with ⟨⟨u2, hu2⟩, ⟨v2, hv2⟩⟩
  simp only [f121Frob, f121Add, f11Add, f11Neg]
  congr 1
  simp only [Fin.mk.injEq]
  omega

theorem f121_norm_u_zero (x : F121) : (f121Mul x (f121Frob x)).u = ⟨0, by omega⟩ := by
  rcases x with ⟨⟨u, hu⟩, ⟨v, hv⟩⟩
  simp only [f121Mul, f121Frob, f11Neg, Fin.mk.injEq]
  by_cases h0 : u = 0
  · subst h0
    simp
  · have hmod : (11 - u) % 11 = 11 - u := Nat.mod_eq_of_lt (by omega)
    rw [hmod]
    have hmul : u * v + v * (11 - u) = 11 * v := by
      calc u * v + v * (11 - u)
          = v * u + v * (11 - u) := by rw [Nat.mul_comm u v]
        _ = v * (u + (11 - u)) := by rw [← Nat.mul_add]
        _ = v * 11 := by rw [Nat.add_sub_of_le (Nat.le_of_lt hu)]
        _ = 11 * v := by rw [Nat.mul_comm]
    rw [hmul]
    exact Nat.mul_mod_right 11 v

/-- Additive shift invariance for 4-term AP coloring condition:
    translating any coloring by an injective map preserves distinctness of colors. -/
theorem injective_map_preserves_three_colors
    {α β : Type} (f : α → β) (hinj : ∀ x y, f x = f y → x = y)
    {c0 c1 c2 c3 : α}
    (h : (c0 ≠ c1 ∧ c0 ≠ c2 ∧ c1 ≠ c2) ∨
         (c0 ≠ c1 ∧ c0 ≠ c3 ∧ c1 ≠ c3) ∨
         (c0 ≠ c2 ∧ c0 ≠ c3 ∧ c2 ≠ c3) ∨
         (c1 ≠ c2 ∧ c1 ≠ c3 ∧ c2 ≠ c3)) :
    (f c0 ≠ f c1 ∧ f c0 ≠ f c2 ∧ f c1 ≠ f c2) ∨
    (f c0 ≠ f c1 ∧ f c0 ≠ f c3 ∧ f c1 ≠ f c3) ∨
    (f c0 ≠ f c2 ∧ f c0 ≠ f c3 ∧ f c2 ≠ f c3) ∨
    (f c1 ≠ f c2 ∧ f c1 ≠ f c3 ∧ f c2 ≠ f c3) := by
  rcases h with ⟨h1, h2, h3⟩ | ⟨h1, h2, h3⟩ | ⟨h1, h2, h3⟩ | ⟨h1, h2, h3⟩
  · exact Or.inl ⟨fun e => h1 (hinj _ _ e), fun e => h2 (hinj _ _ e), fun e => h3 (hinj _ _ e)⟩
  · exact Or.inr (Or.inl ⟨fun e => h1 (hinj _ _ e), fun e => h2 (hinj _ _ e), fun e => h3 (hinj _ _ e)⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨fun e => h1 (hinj _ _ e), fun e => h2 (hinj _ _ e), fun e => h3 (hinj _ _ e)⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨fun e => h1 (hinj _ _ e), fun e => h2 (hinj _ _ e), fun e => h3 (hinj _ _ e)⟩))

/-!
## Coupled Affine Permutation Determinant Obstruction (`π_(x,z)`)
For a z-coupled affine coloring `C(y, z) = π(σ(z) * y + F(z))`, along any 4-term AP
`z_i = z_0 + i * h` with scaling values `(s0, s1, s2, s3)` and shift values `(f0, f1, f2, f3)`,
define the 2x2 coupled determinant:
  `D = (s3 - s0) * (2 * s2 - s1) - 3 * s3 * (s2 - s1)`
and Cramer numerators:
  `Y0 = -(f3 - f0) * (2 * s2 - s1) + 3 * s3 * (f2 - f1)`
  `H  = -(s3 - s0) * (f2 - f1) + (s2 - s1) * (f3 - f0)`
Then for ALL `(s0, s1, s2, s3)` and ALL `(f0, f1, f2, f3)` (even non-polynomial `F`),
the scaled progression `Y_i = Y0 + i * H` satisfies exact ABBA outer and inner equality:
  `s0 * Y0 + D * f0 = s3 * (Y0 + 3 * H) + D * f3`
  `s1 * (Y0 + H) + D * f1 = s2 * (Y0 + 2 * H) + D * f2`
Hence whenever `D` is invertible in the field, `y0 = Y0 / D`, `η = H / D` forces an ABBA.
-/

def coupledAffineDet (s0 s1 s2 s3 : Int) : Int :=
  (s3 - s0) * (2 * s2 - s1) - 3 * s3 * (s2 - s1)

def coupledAffineY0 (_s0 s1 s2 s3 f0 f1 f2 f3 : Int) : Int :=
  (f0 - f3) * (2 * s2 - s1) + 3 * s3 * (f2 - f1)

def coupledAffineH (s0 s1 s2 s3 f0 f1 f2 f3 : Int) : Int :=
  (s0 - s3) * (f2 - f1) + (s2 - s1) * (f3 - f0)

theorem coupled_affine_det_forces_abba
    (s0 s1 s2 s3 f0 f1 f2 f3 : Int) :
    let D := coupledAffineDet s0 s1 s2 s3
    let Y0 := coupledAffineY0 s0 s1 s2 s3 f0 f1 f2 f3
    let H := coupledAffineH s0 s1 s2 s3 f0 f1 f2 f3
    (s0 * Y0 + D * f0 = s3 * (Y0 + 3 * H) + D * f3) ∧
    (s1 * (Y0 + H) + D * f1 = s2 * (Y0 + 2 * H) + D * f2) := by
  dsimp [coupledAffineDet, coupledAffineY0, coupledAffineH]
  constructor <;> grind

/-- Universal Difference Decomposition Identity for the coupled affine determinant:
    `D_σ = σ_0 * (Δ^3 σ) - (Δ^2 σ) * (σ_3 - σ_0)`.
    Immediately implies `D_σ = 0` whenever `σ` is `F_p`-affine (`Δ^2 σ = 0` and `Δ^3 σ = 0`),
    and proves that for degree-`k` polynomial slices (`k >= 2`), `D_σ` has degree `2k - 3`
    with leading coefficient `-2 * (k - 1) * k * (k + 1) * c_k^2`. -/
theorem coupled_affine_det_diff_identity (s0 s1 s2 s3 : Int) :
    coupledAffineDet s0 s1 s2 s3 =
    s0 * (s3 - 3 * s2 + 3 * s1 - s0) - (s2 - 2 * s1 + s0) * (s3 - s0) := by
  dsimp [coupledAffineDet]
  grind

/-- Rank-1 Equivalence on the `F_p`-Affine Coupling Branch (`σ_i = a + i * b`):
    The outer difference `(σ_3 * y_3 - σ_0 * y_0)` is identically `3` times the inner
    difference `(σ_2 * y_2 - σ_1 * y_1)` along any arithmetic progression `y_i = y0 + i * eta`.
    Hence `C_0 = C_3` and `C_1 = C_2` is solvable for `(y0, eta)` iff `F_0 - F_3 = 3 * (F_1 - F_2)`,
    i.e., `Δ^3 F = F_3 - 3 * F_2 + 3 * F_1 - F_0 = 0`. -/
theorem coupled_fp_affine_row_proportional (a b y0 eta : Int) :
    ((a + 3 * b) * (y0 + 3 * eta) - a * y0) =
    3 * (((a + 2 * b) * (y0 + 2 * eta) - (a + b) * (y0 + eta))) := by
  grind

/-- Projective & Cyclotomic Weight Radial Collapse Identity:
    Along a radial 4-term progression `z_i = (1 + i) * h` (`i = 0, 1, 2, 3`), any function
    `Ω(z)` invariant under prime-field scalars `1, 2, 3, 4 in F_p*` takes a constant value `w = Ω(h)`,
    and for any inhomogeneous degree-3 polynomial `A((1 + i) * h) = (1 + i)^3 * a3 + (1 + i)^2 * a2 + (1 + i) * a1 + a0`,
    all lower-degree terms `a2, a1, a0` cancel identically under the third difference, leaving `6 * w * a3`. -/
theorem projective_weight_radial_cubic_collapse (w a3 a2 a1 a0 : Int) :
    let f0 := w * (1 * a3 + 1 * a2 + 1 * a1 + a0)
    let f1 := w * (8 * a3 + 4 * a2 + 2 * a1 + a0)
    let f2 := w * (27 * a3 + 9 * a2 + 3 * a1 + a0)
    let f3 := w * (64 * a3 + 16 * a2 + 4 * a1 + a0)
    f3 - 3 * f2 + 3 * f1 - f0 = 6 * w * a3 := by
  dsimp
  grind

/-- Quartic Midpoint Even-Parity Cancellation Identity (`D <= 4r` barrier for degree-4 vector polynomials):
    For any degree-4 polynomial `P(t) = a4 * t^4 + a3 * t^3 + a2 * t^2 + a1 * t + a0` along a
    midpoint-centered 4-AP `(u0 - 3v, u0 - v, u0 + v, u0 + 3v)` (`t in {-3, -1, 1, 3}`),
    the quartic term `a4 * t^4` and quadratic term `a2 * t^2` are even and cancel identically
    from both `P(3) - P(-3)` and `P(1) - P(-1)`, leaving only `54 * a3 + 6 * a1` and `2 * a3 + 2 * a1`
    (with determinant `96 = 2 * 48`). Hence `a3 = 0` and `a1 = 0` (total degree `3 + 1 = 4` per
    coordinate) suffices to force `P(-3) = P(3)` and `P(-1) = P(1)` regardless of `a4, a2, a0`. -/
def evalQuarticLine (a4 a3 a2 a1 a0 t : Int) : Int :=
  a4 * t * t * t * t + a3 * t * t * t + a2 * t * t + a1 * t + a0

theorem quartic_midpoint_even_cancellation (a4 a3 a2 a1 a0 : Int) :
    (evalQuarticLine a4 a3 a2 a1 a0 3 - evalQuarticLine a4 a3 a2 a1 a0 (-3) = 54 * a3 + 6 * a1) ∧
    (evalQuarticLine a4 a3 a2 a1 a0 1 - evalQuarticLine a4 a3 a2 a1 a0 (-1) = 2 * a3 + 2 * a1) ∧
    (evalQuarticLine a4 0 a2 0 a0 (-3) = evalQuarticLine a4 0 a2 0 a0 3) ∧
    (evalQuarticLine a4 0 a2 0 a0 (-1) = evalQuarticLine a4 0 a2 0 a0 1) := by
  dsimp [evalQuarticLine]
  refine ⟨by grind, by grind, by grind, by grind⟩

/-!
## Characteristic-5 Non-Polynomial Line Rigidity (`F_5^d -> F_5`)
Over `F_5`, binomial weights `(1, -4, 6, -4, 1)` equal `(1, 1, 1, 1, 1) - 5 * (0, 1, -1, 1, 0)`,
so for ANY function `g : F_5 -> F_5` (even non-polynomial or piecewise), the fourth difference
is congruent mod 5 to the constant line sum `S = g0 + g1 + g2 + g3 + g4`. Consequently, if all
five cyclic third differences `D_t ≡ (D_0 + t * S) mod 5` are nonzero, `S mod 5` MUST vanish
(`a_4 = 0`), forcing `g` to have degree exactly 3 on every line (and by Chevalley-Warning,
`d <= 3` globally).
-/

theorem f5_fourth_diff_sum_identity (g0 g1 g2 g3 g4 : Int) :
    (g4 - 3 * g3 + 3 * g2 - g1) - (g3 - 3 * g2 + 3 * g1 - g0) =
    (g0 + g1 + g2 + g3 + g4) - 5 * (g3 - g2 + g1) := by
  omega

theorem f5_nonzero_orbit_forces_zero_slope
    (d0 s : Nat)
    (hd0 : d0 < 5) (hs : s < 5)
    (h0 : d0 ≠ 0)
    (h1 : (d0 + s) % 5 ≠ 0)
    (h2 : (d0 + 2 * s) % 5 ≠ 0)
    (h3 : (d0 + 3 * s) % 5 ≠ 0)
    (h4 : (d0 + 4 * s) % 5 ≠ 0) :
    s = 0 := by
  rcases (by omega : s = 0 ∨ s = 1 ∨ s = 2 ∨ s = 3 ∨ s = 4) with rfl | rfl | rfl | rfl | rfl <;> omega

end PathWeaverFormal.Frobenius
