import PathWeaverFormal.TwoDigitCyclicLift
import Lean.Elab.Tactic.Grind

namespace PathWeaverFormal.Jsp158.CyclicTailProduct

/-- The cyclic template colors the remainder; the interval template colors the quotient. -/
def color (m r : Nat) (low : Nat → Nat) (tail : Array Nat) (z : Nat) : Nat :=
  low (z % m) + r * getColor tail (z / m)

private theorem decode (f : Nat → Nat) {a b c d : Nat}
    (h : AtLeastThreeColors (f a) (f b) (f c) (f d)) :
    AtLeastThreeColors a b c d := by
  unfold AtLeastThreeColors at *
  grind

/-- A cyclic m-template and an arbitrary finite interval tail cover their product
    interval, including an empty tail. The modulus need only be positive. -/
theorem interval {m r s : Nat} (hm : 0 < m) (low : Nat → Nat)
    (lowBound : ∀ x, x < m → low x < r) (cyclic : CyclicThreeColors m low)
    (tail : Array Nat) (legal : IsFourAPFree3 tail) (tailBound : AllColorsBelow tail s) :
    ∃ colors : Array Nat, colors.size = m * tail.size ∧
      IsFourAPFree3 colors ∧ AllColorsBelow colors (r*s) := by
  let paint := color m r low tail
  have hr : 0 < r := Nat.lt_of_le_of_lt (Nat.zero_le _) (lowBound 0 hm)
  have remainder (z : Nat) : paint z % r = low (z%m) := by
    simp only [paint, color, Nat.add_mul_mod_self_left, Nat.mod_eq_of_lt (lowBound _ (Nat.mod_lt z hm))]
  have quotient (z : Nat) : paint z / r = getColor tail (z/m) := by
    simp only [paint, color, Nat.add_mul_div_left _ _ hr,
      Nat.div_eq_of_lt (lowBound _ (Nat.mod_lt z hm)), Nat.zero_add]
  have indexOk (z : Nat) (hz : z < m * tail.size) : z/m < tail.size :=
    (Nat.div_lt_iff_lt_mul hm).2 (by simpa only [Nat.mul_comm m tail.size] using hz)
  let colors := Array.ofFn (fun i : Fin (m * tail.size) => paint i.val)
  have size : colors.size = m * tail.size := by simp [colors]
  have entry (z : Nat) (hz : z < m * tail.size) : getColor colors z = paint z := by
    simp [colors, getColor, hz]
  refine ⟨colors, size, ?_, ?_⟩
  · intro a d hd last
    rw [size] at last
    rw [entry a (by omega), entry (a+d) (by omega), entry (a+2*d) (by omega), entry (a+3*d) last]
    by_cases hz : d % m = 0
    · have full : m * (d/m) = d := by simpa [hz] using Nat.mod_add_div d m
      have positive : 0 < d/m := by
        apply Nat.pos_of_ne_zero
        intro zero
        simp [zero] at full
        omega
      have along (j : Nat) : (a+j*d)/m = a/m+j*(d/m) := by
        calc
          _ = (a+m*(j*(d/m)))/m := by rw [← Nat.mul_left_comm j m (d/m), full]
          _ = _ := Nat.add_mul_div_left _ _ hm
      apply decode (fun z => z/r)
      simp only [quotient, show (a+d)/m = a/m+d/m by simpa using along 1, along 2, along 3]
      exact legal _ _ positive (by rw [← along 3]; exact indexOk _ last)
    · apply decode (fun z => z%r)
      simpa only [remainder] using cyclic a d hz
  · intro z hz
    rw [size] at hz
    rw [entry z hz]
    have hl := lowBound _ (Nat.mod_lt z hm)
    have hh := tailBound _ (indexOk z hz)
    calc
      paint z < r * (getColor tail (z/m) + 1) := by
        simp only [paint, color, Nat.mul_succ]
        omega
      _ ≤ r*s := Nat.mul_le_mul_left _ hh

/-- On the three-cycle, any nonzero step visits all three residues in its first three positions. -/
theorem cyclicThree : CyclicThreeColors 3 id := by
  intro a d hd
  exact Or.inl ⟨by simp only [id_eq]; omega, by simp only [id_eq]; omega,
    by simp only [id_eq]; omega⟩

/-- In interval-witness form this gives h(3n) ≤ 3 h(n). -/
theorem triple {s : Nat} (tail : Array Nat) (legal : IsFourAPFree3 tail)
    (bounded : AllColorsBelow tail s) :
    ∃ colors : Array Nat, colors.size = 3 * tail.size ∧
      IsFourAPFree3 colors ∧ AllColorsBelow colors (3*s) :=
  interval (by decide : 0 < 3) id (fun _ h => h) cyclicThree tail legal bounded

#print axioms interval
#print axioms cyclicThree
#print axioms triple

end PathWeaverFormal.Jsp158.CyclicTailProduct
