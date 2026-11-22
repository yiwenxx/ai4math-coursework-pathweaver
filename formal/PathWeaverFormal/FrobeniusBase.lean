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

end PathWeaverFormal.Frobenius
