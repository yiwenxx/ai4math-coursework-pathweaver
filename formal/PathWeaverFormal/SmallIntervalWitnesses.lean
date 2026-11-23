import PathWeaverFormal.Jsp158Coloring

/-! Finite interval witnesses for the original four-term progression coloring
problem. Array index i represents integer position i+1. -/
namespace PathWeaverFormal.Jsp158.SmallInterval

/-- Arhan Canli's public seven-color witness, commit aebf971.
https://github.com/arhancanli/quantavane-erdos-results/blob/aebf97111b16e7e3b84aaff856f573e8cc1f01ed/160/witness/k7_N77.txt -/
def seven77 : Array Nat := #[
  1, 1, 6, 2, 1, 1, 0, 4, 4, 6, 3, 5, 3, 4,
  5, 2, 1, 2, 0, 3, 3, 4, 2, 2, 5, 0, 5, 6,
  6, 0, 4, 3, 4, 6, 3, 1, 5, 1, 3, 5, 2, 0,
  2, 1, 1, 0, 4, 2, 2, 5, 4, 5, 6, 6, 0, 4,
  1, 4, 6, 3, 1, 5, 0, 4, 0, 3, 3, 1, 2, 6,
  2, 1, 6, 2, 5, 2, 0]

/-- The local eight-color refinement, archived in
`results/jsp158_eight_color_interval/witness.json`. Its 97-position starting
word comes from Scott Schluer's repository at commit f37b5fc.
https://github.com/scottschluer/erdos160/blob/f37b5fc28bf9c166a32b337d7a6631a89fc3a350/results/erdos160-small-values/witnesses/k8_N97.txt -/
def eight98 : Array Nat := #[
  0, 5, 5, 4, 0, 4, 1, 1, 6, 3, 5, 0, 5, 7,
  2, 3, 7, 6, 6, 3, 0, 0, 2, 1, 1, 5, 4, 4,
  7, 2, 4, 2, 6, 7, 6, 5, 5, 4, 3, 0, 3, 5,
  2, 6, 7, 0, 3, 7, 7, 0, 1, 1, 4, 6, 2, 6,
  1, 2, 2, 5, 4, 2, 4, 3, 3, 5, 0, 5, 3, 4,
  1, 1, 5, 4, 1, 6, 0, 7, 5, 4, 0, 3, 6, 7,
  7, 1, 2, 7, 6, 2, 6, 0, 0, 2, 7, 3, 7, 4]

set_option maxRecDepth 8192
set_option maxHeartbeats 3000000

theorem seven77_valid :
    seven77.size = 77 ∧ IsFourAPFree3 seven77 ∧ AllColorsBelow seven77 7 :=
  ⟨rfl, checkFourAPFree3_sound _ (by decide +kernel), checkColorsBelow_sound _ _ (by decide +kernel)⟩

theorem eight98_valid :
    eight98.size = 98 ∧ IsFourAPFree3 eight98 ∧ AllColorsBelow eight98 8 :=
  ⟨rfl, checkFourAPFree3_sound _ (by decide +kernel), checkColorsBelow_sound _ _ (by decide +kernel)⟩

#print axioms eight98_valid

end PathWeaverFormal.Jsp158.SmallInterval
