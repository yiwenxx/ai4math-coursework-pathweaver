import PathWeaverFormal.Jsp158Coloring

/-! A nine-color witness on the first 137 positive integers. Array index
`i` denotes position `i+1`. -/
namespace PathWeaverFormal.Jsp158.NineColorInterval

def nine137 : Array Nat := #[
  0, 1, 3, 7, 2, 1, 5, 0, 2, 8, 7, 4, 6, 7, 2, 0, 4, 6,
  0, 1, 5, 1, 4, 3, 5, 5, 8, 1, 6, 5, 2, 6, 2, 8, 8, 6,
  3, 3, 0, 7, 4, 0, 4, 5, 7, 3, 8, 3, 7, 2, 1, 0, 1, 2,
  8, 7, 4, 6, 7, 2, 0, 4, 6, 0, 1, 5, 1, 4, 3, 5, 5, 8,
  1, 6, 5, 2, 6, 2, 8, 8, 6, 3, 3, 0, 7, 4, 0, 4, 5, 7,
  3, 8, 3, 7, 2, 1, 0, 1, 2, 8, 7, 4, 6, 7, 2, 0, 4, 6,
  0, 1, 5, 1, 4, 3, 5, 5, 8, 1, 6, 5, 2, 6, 2, 8, 8, 6,
  3, 3, 0, 7, 4, 0, 4, 5, 7, 5, 6]

set_option maxRecDepth 16384
set_option maxHeartbeats 10000000

/-- Every positive-step four-term arithmetic progression in the displayed
interval has at least three colors, and all colors are below nine. -/
theorem nine137_valid :
    nine137.size = 137 ∧ IsFourAPFree3 nine137 ∧ AllColorsBelow nine137 9 :=
  ⟨rfl, checkFourAPFree3_sound _ (by decide +kernel),
    checkColorsBelow_sound _ _ (by decide +kernel)⟩

#print axioms nine137_valid

end PathWeaverFormal.Jsp158.NineColorInterval
