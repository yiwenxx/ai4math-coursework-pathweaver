import PathWeaverFormal.Jsp158Coloring
import Init.Data.Array.Lemmas
import Init.Data.Nat.Div.Lemmas

namespace PathWeaverFormal.Jsp158

/-- Legality of a digit template on ℤ/pℤ, using natural representatives. -/
def CyclicThreeColors (p : Nat) (c : Nat → Nat) : Prop :=
  ∀ a d : Nat, d % p ≠ 0 →
    AtLeastThreeColors (c (a % p)) (c ((a + d) % p))
      (c ((a + 2*d) % p)) (c ((a + 3*d) % p))

/-- The two color indices are packed in base r, with the low digit first. -/
def twoDigitColor (p r : Nat) (c : Nat → Nat) (n : Nat) : Nat :=
  c (n % p) + r * c ((n / p) % p)

private theorem three_of_decoding (f : Nat → Nat) {a b c d : Nat}
    (h : AtLeastThreeColors (f a) (f b) (f c) (f d)) : AtLeastThreeColors a b c d := by
  have lift {x y : Nat} : f x ≠ f y → x ≠ y := fun hn e => hn (congrArg f e)
  rcases h with ⟨h₁,h₂,h₃⟩ | ⟨h₁,h₂,h₃⟩ | ⟨h₁,h₂,h₃⟩ | ⟨h₁,h₂,h₃⟩
  · exact Or.inl ⟨lift h₁,lift h₂,lift h₃⟩
  · exact Or.inr (Or.inl ⟨lift h₁,lift h₂,lift h₃⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨lift h₁,lift h₂,lift h₃⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨lift h₁,lift h₂,lift h₃⟩))

private theorem twoDigit_progression {p r : Nat} (hp : 0 < p) (hr : 0 < r)
    (c : Nat → Nat) (bounded : ∀ x, x < p → c x < r) (cyclic : CyclicThreeColors p c)
    (a d : Nat) (hd : 0 < d) (hstep : d < p*p) :
    AtLeastThreeColors (twoDigitColor p r c a) (twoDigitColor p r c (a+d))
      (twoDigitColor p r c (a+2*d)) (twoDigitColor p r c (a+3*d)) := by
  by_cases hz : d % p = 0
  · have decomp : p*(d/p) = d := by simpa [hz] using Nat.mod_add_div d p
    have lt : d/p < p := (Nat.div_lt_iff_lt_mul hp).2 hstep
    have nz : (d/p) % p ≠ 0 := by
      rw [Nat.mod_eq_of_lt lt]
      intro hzero
      simp [hzero] at decomp
      omega
    have along (k : Nat) : (a+k*d)/p = a/p+k*(d/p) := by
      calc
        (a+k*d)/p = (a+p*(k*(d/p)))/p := by rw [← Nat.mul_left_comm k p (d/p), decomp]
        _ = a/p+k*(d/p) := Nat.add_mul_div_left _ _ hp
    have upper (n : Nat) : twoDigitColor p r c n / r = c ((n/p) % p) := by
      rw [twoDigitColor, Nat.add_mul_div_left _ _ hr,
        Nat.div_eq_of_lt (bounded _ (Nat.mod_lt n hp)), Nat.zero_add]
    apply three_of_decoding (fun n => n/r)
    simp only [upper]
    rw [show (a+d)/p = a/p+d/p by simpa using along 1, along 2, along 3]
    exact cyclic (a/p) (d/p) nz
  · have lower (n : Nat) : twoDigitColor p r c n % r = c (n % p) := by
      rw [twoDigitColor, Nat.add_mul_mod_self_left, Nat.mod_eq_of_lt (bounded _ (Nat.mod_lt n hp))]
    apply three_of_decoding (fun n => n % r)
    simpa only [lower] using cyclic a d hz

private theorem twoDigit_bound {p r : Nat} (hp : 0 < p) (c : Nat → Nat)
    (bounded : ∀ x, x < p → c x < r) (n : Nat) : twoDigitColor p r c n < r*r := by
  have hl := bounded _ (Nat.mod_lt n hp)
  have hh := bounded _ (Nat.mod_lt (n/p) hp)
  calc
    twoDigitColor p r c n < r*(c ((n/p) % p)+1) := by
      rw [twoDigitColor, Nat.mul_succ]
      omega
    _ ≤ r*r := Nat.mul_le_mul_left _ hh

/-- The original array specification on any interval of length at most 3p².
    No primality assumption is needed for the lift. -/
theorem twoDigit_interval {p r N : Nat} (hp : 0 < p) (hr : 0 < r) (capacity : N ≤ 3*(p*p))
    (c : Nat → Nat) (bounded : ∀ x, x < p → c x < r) (cyclic : CyclicThreeColors p c) :
    ∃ colors : Array Nat, colors.size = N ∧ IsFourAPFree3 colors ∧ AllColorsBelow colors (r*r) := by
  let colors := Array.ofFn (fun i : Fin N => twoDigitColor p r c i.val)
  have hsize : colors.size = N := by simp [colors]
  have entry (n : Nat) (hn : n < N) : getColor colors n = twoDigitColor p r c n := by
    simp [getColor, colors, hn]
  refine ⟨colors, hsize, ?_, ?_⟩
  · intro a d hd ha
    rw [hsize] at ha
    rw [entry a (by omega), entry (a+d) (by omega), entry (a+2*d) (by omega),
      entry (a+3*d) ha]
    exact twoDigit_progression hp hr c bounded cyclic a d hd (by omega)
  · intro n hn
    rw [hsize] at hn
    rw [entry n hn]
    exact twoDigit_bound hp c bounded n

/-- The input template and its palette bound are the hypotheses certified by
    the separate modular-arithmetic certificate for the 50343rd-power map. -/
theorem criticalSquare_10pow18 (c : Nat → Nat)
    (bounded : ∀ x, x < 578743129 → c x < 11496)
    (cyclic : CyclicThreeColors 578743129 c) :
    ∃ colors : Array Nat, colors.size = 10^18 ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 :=
  twoDigit_interval (p := 578743129) (r := 11496) (N := 10^18)
    (by decide) (by decide) (by decide) c bounded cyclic

end PathWeaverFormal.Jsp158
