import PathWeaverFormal.CriticalSquareIntervals
import Lean.PrivateName

/-! The zero column of the critical template can use the entire palette.
The collision proof is imported once. This module only reasons about its
digit colors and the new length bound. -/
namespace PathWeaverFormal.Jsp158.OddPower.CriticalSquare.Boundary

open Fin.NatCast
private abbrev p := 578743129
private abbrev r := 11496
private abbrev F := Fin p

local macro "boundary_omega" : tactic => `(tactic| (simp only [p,r] at * <;> omega))

open Lean in
local macro "templateFact%" n:ident : term => do
  let name := mkPrivateNameCore `PathWeaverFormal.OddPowerCollisionLift
    (`PathWeaverFormal.Jsp158.OddPower ++ n.getId)
  return ⟨(mkIdent name).raw⟩

private def label := (templateFact% indexedColor) 50343 criticalPalette
private def digit (n : Nat) := label (Fin.ofNat p n)

private theorem digit_lt (n : Nat) : digit n < r := by
  change (if Fin.ofNat p n = 0 then 0 else criticalPalette.idxOf ((Fin.ofNat p n)^50343)) < r
  split
  · decide
  · next h =>
    have size : criticalPalette.length=r := by simp [criticalPalette]
    exact size ▸ List.idxOf_lt_length_of_mem ((templateFact% critical_image) (Fin.ofNat p n) h)

/-- A fixed replacement at zero can be any natural number. -/
private theorem flexible (v : Nat) :
    CyclicThreeColors p (fun n => if n % p=0 then v else digit n) := by
  let c (x : F) := if x=0 then v else label x
  have ok : CyclicThreeColors p (fun n => c (Fin.ofNat p n)) := by
    apply cyclic_of_every_step
    apply every_step (by decide) 50343 criticalRoots (templateFact% critical_units)
      (templateFact% critical_covers) verifiedCollisions critical_zero c
    intro x y hx hy eq
    simp only [c, ite_eq_right hx, ite_eq_right hy] at eq
    exact (templateFact% indexed_reflects) criticalPalette (templateFact% critical_image) x y hx hy eq
  simpa only [c, digit, Fin.ext_iff, Fin.val_zero, Fin.ofNat] using ok

private theorem two_labels {a b c d : Nat} (bad : ¬ AtLeastThreeColors a b c d) :
    ∃ u v, (a=u ∨ a=v) ∧ (b=u ∨ b=v) ∧ (c=u ∨ c=v) ∧ (d=u ∨ d=v) := by
  unfold AtLeastThreeColors at bad
  by_cases ab : a=b
  · by_cases ac : a=c
    · exact ⟨a,d,by grind⟩
    · exact ⟨a,c,by grind⟩
  · exact ⟨a,b,by grind⟩

private theorem decode (D : Nat → Nat) {a b c d : Nat}
    (ok : AtLeastThreeColors (D a) (D b) (D c) (D d)) : AtLeastThreeColors a b c d := by
  unfold AtLeastThreeColors at *
  grind

/-- Positions over zero may vary independently, even between periods. -/
private theorem free_step (g : Nat → Nat)
    (same : ∀ n, n%p ≠ 0 → g n=digit (n%p)) (a d : Nat) (hd : d%p ≠ 0) :
    AtLeastThreeColors (g a) (g (a+d)) (g (a+2*d)) (g (a+3*d)) := by
  apply Classical.byContradiction
  intro bad
  obtain ⟨u,v,ha,hb,hc,he⟩ := two_labels bad
  let f (n : Nat) := if n%p=0 then u else digit (n%p)
  have member (n : Nat) (hn : g n=u ∨ g n=v) : f n=u ∨ f n=v := by
    by_cases h : n%p=0
    · simp [f,h]
    · simpa only [f, ite_eq_right h, ← same _ h] using hn
  have valid := flexible u a d hd
  simp only [Nat.mod_mod] at valid
  change AtLeastThreeColors (f a) (f (a+d)) (f (a+2*d)) (f (a+3*d)) at valid
  have := member _ ha; have := member _ hb; have := member _ hc; have := member _ he
  unfold AtLeastThreeColors at valid
  grind

private def upper (z : Nat) := if z%p=0 then z/p%3 else digit (z%p)

private theorem upper_lt (z : Nat) : upper z < r := by
  unfold upper
  split
  · have := Nat.mod_lt (z/p) (by decide : 0 < 3); boundary_omega
  · exact digit_lt _

private theorem upper_step (a d : Nat) (hd : 0 < d) (last : a+3*d < 3*p+1) :
    AtLeastThreeColors (upper a) (upper (a+d)) (upper (a+2*d)) (upper (a+3*d)) := by
  by_cases hz : d%p=0
  · have ed : d=p := by boundary_omega
    have ea : a=0 := by boundary_omega
    subst a d
    unfold AtLeastThreeColors
    decide +kernel
  · exact free_step upper (by intro n hn; simp [upper,hn]) a d hz

private def tag (t : Nat) := if t<2 then 0 else if t=2 then 1 else 2
private def zeroColumn (z : Nat) := digit (z%p) + r*tag (z/p)

private theorem zero_low (n : Nat) : zeroColumn n % r = digit (n%p) := by
  rw [zeroColumn, Nat.add_mul_mod_self_left, Nat.mod_eq_of_lt (digit_lt _)]

private theorem zero_high (n : Nat) : zeroColumn n / r = tag (n/p) := by
  rw [zeroColumn, Nat.add_mul_div_left _ _ (by decide), Nat.div_eq_of_lt (digit_lt _), Nat.zero_add]

private theorem zero_step (a d : Nat) (hd : 0 < d) (last : a+3*d < 3*p+2) :
    AtLeastThreeColors (zeroColumn a) (zeroColumn (a+d)) (zeroColumn (a+2*d)) (zeroColumn (a+3*d)) := by
  by_cases hz : d%p=0
  · apply decode (fun n => n/r)
    simp only [zero_high]
    have ed : d=p := by boundary_omega
    have ea : a=0 ∨ a=1 := by boundary_omega
    subst d
    rcases ea with rfl | rfl <;> unfold AtLeastThreeColors <;> decide +kernel
  · apply decode (fun n => n%r)
    simp only [zero_low]
    exact free_step (fun n => digit (n%p)) (by intros; rfl) a d hz

private def boundaryColor (n : Nat) :=
  if n%p=0 then zeroColumn (n/p) else digit (n%p)+r*upper (n/p)

private theorem boundary_lt (n : Nat) : boundaryColor n < 132158016 := by
  unfold boundaryColor
  split
  · unfold zeroColumn
    have h := digit_lt (n/p%p)
    have htop : tag (n/p/p) ≤ 2 := by unfold tag; split <;> first | decide | split <;> decide
    boundary_omega
  · have := digit_lt (n%p); have := upper_lt (n/p); boundary_omega

private theorem boundary_step (a d : Nat) (hd : 0 < d) (last : a+3*d < 3*p*p+p+1) :
    AtLeastThreeColors (boundaryColor a) (boundaryColor (a+d))
      (boundaryColor (a+2*d)) (boundaryColor (a+3*d)) := by
  by_cases hz : d%p=0
  · have decomp : p*(d/p)=d := by simpa [hz] using Nat.mod_add_div d p
    have positive : 0 < d/p := by boundary_omega
    have quotient (k : Nat) : (a+k*d)/p=a/p+k*(d/p) := by
      calc
        (a+k*d)/p = (a+p*(k*(d/p)))/p := by rw [← Nat.mul_left_comm k p (d/p), decomp]
        _ = _ := Nat.add_mul_div_left _ _ (by decide)
    have rem (k : Nat) : (a+k*d)%p=a%p := by
      rw [← decomp, Nat.mul_left_comm k p, Nat.add_mul_mod_self_left]
    simp only [boundaryColor, rem, show (a+d)%p=a%p by simpa using rem 1,
      quotient, show (a+d)/p=a/p+d/p by simpa using quotient 1]
    by_cases hx : a%p=0
    · simp only [hx, ite_true]
      exact zero_step (a/p) (d/p) positive (by boundary_omega)
    · simp only [ite_eq_right hx]
      apply decode (fun n => n/r)
      have get (z : Nat) : (digit (a%p)+r*upper z)/r=upper z := by
        rw [Nat.add_mul_div_left _ _ (by decide), Nat.div_eq_of_lt (digit_lt _), Nat.zero_add]
      simp only [get]
      exact upper_step (a/p) (d/p) positive (by boundary_omega)
  · apply decode (fun n => n%r)
    apply free_step _ _ a d hz
    intro n hn
    simp only [boundaryColor, ite_eq_right hn, Nat.add_mul_mod_self_left, Nat.mod_eq_of_lt (digit_lt _)]

/-- The extended no-extra-color range in the original array specification. -/
theorem interval_up_to (N : Nat) (sizeBound : N ≤ 1004830828672875053) :
    ∃ colors : Array Nat, colors.size = N ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 := by
  let colors := Array.ofFn (fun i : Fin N => boundaryColor i.val)
  have hsize : colors.size=N := by simp [colors]
  have entry (n : Nat) (hn : n<N) : getColor colors n=boundaryColor n := by simp [colors,getColor,hn]
  refine ⟨colors,hsize,?_,?_⟩
  · intro a d hd ha
    rw [hsize] at ha
    rw [entry a (by omega), entry (a+d) (by omega), entry (a+2*d) (by omega), entry (a+3*d) ha]
    exact boundary_step a d hd (by boundary_omega)
  · intro n hn
    rw [hsize] at hn
    rw [entry n hn]
    exact boundary_lt n

theorem translated_interval (t : Int) (N : Nat) (sizeBound : N ≤ 1004830828672875053) :
    ∃ c : Int → Nat,
      (∀ z : Int, t ≤ z → z < t+(N : Int) → c z < 132158016) ∧
      (∀ a d : Int, 0 < d → t ≤ a → a+3*d < t+(N : Int) →
        AtLeastThreeColors (c a) (c (a+d)) (c (a+2*d)) (c (a+3*d))) :=
  translate_array t (interval_up_to N sizeBound)

#print axioms translated_interval

end PathWeaverFormal.Jsp158.OddPower.CriticalSquare.Boundary
