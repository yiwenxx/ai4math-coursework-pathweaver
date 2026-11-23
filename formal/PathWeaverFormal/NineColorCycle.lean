import PathWeaverFormal.TwoDigitCyclicLift

namespace PathWeaverFormal.Jsp158.NineColorCycle

/-- The palette entries at residues 0,...,44 of the composite cyclic template. -/
def table : Array Nat := #[
  3,2,5,4,4,1,5,2,2,8,6,8,2,5,3,
  1,3,7,7,8,4,7,5,3,4,2,7,1,6,0,
  4,0,8,5,0,6,6,7,0,6,3,0,8,1,1]

set_option maxRecDepth 8192
set_option maxHeartbeats 3000000

private theorem windows (a d : Fin 45) (hd : d.val ≠ 0) :
    checkTriple (getColor table a.val)
      (getColor table ((a.val + d.val) % 45))
      (getColor table ((a.val + 2*d.val) % 45))
      (getColor table ((a.val + 3*d.val) % 45)) = true := by
  exact (by decide +kernel : ∀ x t : Fin 45, t.val ≠ 0 →
    checkTriple (getColor table x.val)
      (getColor table ((x.val + t.val) % 45))
      (getColor table ((x.val + 2*t.val) % 45))
      (getColor table ((x.val + 3*t.val) % 45)) = true) a d hd

private theorem offset (a k d : Nat) :
    (a % 45 + k*(d % 45)) % 45 = (a + k*d) % 45 := by
  calc
    _ = (a + k*(d % 45)) % 45 := Nat.mod_add_mod _ _ _
    _ = (a + (k*(d % 45)) % 45) % 45 := (Nat.add_mod_mod _ _ _).symm
    _ = (a + (k*d) % 45) % 45 := by rw [Nat.mul_mod_mod]
    _ = _ := Nat.add_mod_mod _ _ _

/-- Every nonzero difference is allowed, including those of additive order three. -/
theorem cyclic45 : CyclicThreeColors 45 (getColor table) := by
  intro a d hd
  have h := checkTriple_sound (windows ⟨a%45, Nat.mod_lt _ (by decide)⟩
    ⟨d%45, Nat.mod_lt _ (by decide)⟩ hd)
  change AtLeastThreeColors (getColor table (a%45))
    (getColor table ((a%45 + d%45)%45)) (getColor table ((a%45 + 2*(d%45))%45))
    (getColor table ((a%45 + 3*(d%45))%45)) at h
  rw [offset a 2 d, offset a 3 d, Nat.mod_add_mod, Nat.add_mod_mod] at h
  exact h

theorem table_bounded : AllColorsBelow table 9 :=
  checkColorsBelow_sound _ _ (by decide +kernel)

def repeated : Array Nat := Array.ofFn (fun i : Fin 135 => getColor table (i.val % 45))

/-- Three periods give the integer endpoint using the same nine colors. -/
theorem interval135 :
    repeated.size = 135 ∧ IsFourAPFree3 repeated ∧ AllColorsBelow repeated 9 := by
  have sz : repeated.size = 135 := by simp [repeated]
  have entry (x : Nat) (hx : x < 135) : getColor repeated x = getColor table (x%45) := by
    simp [getColor, repeated, hx]
  refine ⟨sz, ?_, ?_⟩
  · intro a d hd ha
    rw [sz] at ha
    have small : d < 45 := by omega
    rw [entry a (by omega), entry (a+d) (by omega), entry (a+2*d) (by omega),
      entry (a+3*d) ha]
    exact cyclic45 a d (by rw [Nat.mod_eq_of_lt small]; omega)
  · intro x hx
    rw [sz] at hx
    rw [entry x hx]
    exact table_bounded _ (Nat.mod_lt _ (by decide))

theorem interval6075 :
    ∃ c : Array Nat, c.size = 6075 ∧ IsFourAPFree3 c ∧ AllColorsBelow c 81 :=
  twoDigit_interval (p := 45) (r := 9) (N := 6075) (by decide) (by decide) (by decide)
    (getColor table) (fun x h => table_bounded x h) cyclic45

#print axioms cyclic45
#print axioms interval135
#print axioms interval6075

end PathWeaverFormal.Jsp158.NineColorCycle
