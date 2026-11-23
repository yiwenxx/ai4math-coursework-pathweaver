import PathWeaverFormal.OddPowerCollisionLift
import Lean.PrivateName

/-! Reuse the existing indexing proofs without copying group-theoretic
arguments. The original Lean file predates the module system, so `import all`
cannot open its private helpers. Resolve these five constants by the same
module/name operation Lean uses for `import all`. Each application is still
type-checked by the kernel. -/
namespace PathWeaverFormal.Jsp158.OddPower.CriticalSquare

open Fin.NatCast
open Lean in
local macro "templateFact%" n:ident : term => do
  let name := mkPrivateNameCore `PathWeaverFormal.OddPowerCollisionLift
    (`PathWeaverFormal.Jsp158.OddPower ++ n.getId)
  return ⟨(mkIdent name).raw⟩

/-- The p-digit coloring used by the certificate, with its compact palette. -/
theorem template_of_collisions (checked : collisionCheck 50343 criticalRoots = true) :
    ∃ c : Nat → Nat, (∀ x, x < 578743129 → c x < 11496) ∧
      CyclicThreeColors 578743129 c := by
  let color := (templateFact% indexedColor) 50343 criticalPalette
  refine ⟨fun n => color (n : Fin 578743129), ?_, ?_⟩
  · intro n _
    change (if (n : Fin 578743129) = 0 then 0 else criticalPalette.idxOf ((n : Fin 578743129)^50343)) < _
    split
    · decide
    · next h =>
        have size : criticalPalette.length = 11496 := by simp [criticalPalette]
        exact size ▸ List.idxOf_lt_length_of_mem ((templateFact% critical_image) (n : Fin 578743129) h)
  · exact cyclic_of_every_step color (every_step (by decide) 50343 criticalRoots
      (templateFact% critical_units) (templateFact% critical_covers) checked critical_zero color
      ((templateFact% indexed_reflects) criticalPalette (templateFact% critical_image)))

/-- Every length up to 3p² satisfies the original zero-based array specification. -/
theorem interval_of_collisions (checked : collisionCheck 50343 criticalRoots = true)
    (N : Nat) (capacity : N ≤ 3*(578743129*578743129)) :
    ∃ colors : Array Nat, colors.size = N ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 := by
  obtain ⟨c, bounded, cyclic⟩ := template_of_collisions checked
  exact twoDigit_interval (p := 578743129) (r := 11496) (by decide) (by decide) capacity c bounded cyclic

/-- Every translate in ℤ of such an interval has a coloring with the same
bound. The endpoints are t (included) and t+N (excluded). -/
theorem translate_array {N r : Nat} (t : Int)
    (array : ∃ colors : Array Nat, colors.size = N ∧ IsFourAPFree3 colors ∧ AllColorsBelow colors r) :
    ∃ c : Int → Nat,
      (∀ z : Int, t ≤ z → z < t+(N : Int) → c z < r) ∧
      (∀ a d : Int, 0 < d → t ≤ a → a+3*d < t+(N : Int) →
        AtLeastThreeColors (c a) (c (a+d)) (c (a+2*d)) (c (a+3*d))) := by
  obtain ⟨colors, size, ap, bounded⟩ := array
  refine ⟨fun z => getColor colors (z-t).toNat, ?_, ?_⟩
  · intro z hz hN
    apply bounded
    omega
  · intro a d hd ha hN
    have h := ap (a-t).toNat d.toNat (by omega) (by omega)
    have e1 : (a-t).toNat+d.toNat=(a+d-t).toNat := by omega
    have e2 : (a-t).toNat+2*d.toNat=(a+2*d-t).toNat := by omega
    have e3 : (a-t).toNat+3*d.toNat=(a+3*d-t).toNat := by omega
    simpa only [e1,e2,e3] using h

end PathWeaverFormal.Jsp158.OddPower.CriticalSquare
