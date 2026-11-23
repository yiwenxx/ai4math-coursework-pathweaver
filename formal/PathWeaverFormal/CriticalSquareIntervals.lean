import PathWeaverFormal.CriticalSquareCertificate
import PathWeaverFormal.CriticalSquareTemplate

namespace PathWeaverFormal.Jsp158.OddPower.CriticalSquare

theorem cyclic_template :
    ∃ c : Nat → Nat, (∀ x, x < 578743129 → c x < 11496) ∧ CyclicThreeColors 578743129 c :=
  template_of_collisions verifiedCollisions

/-- Every interval length N up to 1,004,830,828,094,131,923 meets the original
array specification with at most 132,158,016 colors. -/
theorem interval_up_to (N : Nat) (hN : N ≤ 3*(578743129*578743129)) :
    ∃ colors : Array Nat, colors.size = N ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 :=
  interval_of_collisions verifiedCollisions N hN

/-- The same bound on every translated half-open integer interval [t,t+N). -/
theorem translated_interval (t : Int) (N : Nat) (hN : N ≤ 3*(578743129*578743129)) :
    ∃ c : Int → Nat,
      (∀ z : Int, t ≤ z → z < t+(N : Int) → c z < 132158016) ∧
      (∀ a d : Int, 0 < d → t ≤ a → a+3*d < t+(N : Int) →
        AtLeastThreeColors (c a) (c (a+d)) (c (a+2*d)) (c (a+3*d))) :=
  translate_array t (interval_up_to N hN)

#print axioms translated_interval

end PathWeaverFormal.Jsp158.OddPower.CriticalSquare
