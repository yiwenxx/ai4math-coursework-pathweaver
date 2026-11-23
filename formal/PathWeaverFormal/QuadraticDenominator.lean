import Init.Grind.Ring.Field

namespace PathWeaverFormal.QuadraticDenominator

open Lean.Grind

variable {F Color : Type} [Field F]

/-- The four sampled points have one common step with nonzero second coordinate. -/
def HasOrderedABBA (color : F → F → Color) (outer : Color) : Prop :=
  ∃ y t dy dt : F, dt ≠ 0 ∧
    color y t = outer ∧
    color (y + dy) (t + dt) = color (y + 2 * dy) (t + 2 * dt) ∧
    color (y + 3 * dy) (t + 3 * dt) = outer

/-- A shear on a line where the numerator is cubic and the denominator is even. -/
def shear (π : F → Color) (a₃ a₂ a₁ a₀ b₂ b₀ y t : F) : Color :=
  π (y + (a₃ * t^3 + a₂ * t^2 + a₁ * t + a₀) / (b₂ * t^2 + b₀))

/-- Matching the two odd coefficients removes a linear term wherever the denominator
is nonzero, leaving a function of the square of the line parameter. -/
theorem cancelOdd (a₃ a₂ a₁ a₀ b₂ b₀ k Y t : F)
    (h₃ : a₃ = k * b₂) (h₁ : a₁ = k * b₀) (hd : b₂ * t^2 + b₀ ≠ 0) :
    (Y - k * t) + (a₃ * t^3 + a₂ * t^2 + a₁ * t + a₀) / (b₂ * t^2 + b₀) =
      Y + (a₂ * t^2 + a₀) / (b₂ * t^2 + b₀) := by
  rw [Field.add_div hd, Field.add_div hd]
  congr 1
  grind only

/-- The parameters -3s, -s, s, 3s give an ordered ABBA progression for every
prescribed outer value in the image of the color map. -/
theorem matchedCubicABBA (π : F → Color) (a₃ a₂ a₁ a₀ b₂ b₀ k s outer : F)
    (h₃ : a₃ = k * b₂) (h₁ : a₁ = k * b₀) (hstep : 2 * s ≠ 0)
    (hin : b₂ * s^2 + b₀ ≠ 0) (hout : b₂ * (3 * s)^2 + b₀ ≠ 0) :
    HasOrderedABBA (shear π a₃ a₂ a₁ a₀ b₂ b₀) (π outer) := by
  let evenValue (t : F) := (a₂ * t^2 + a₀) / (b₂ * t^2 + b₀)
  let Y := outer - evenValue (3 * s)
  have atPoint (t : F) (ht : b₂ * t^2 + b₀ ≠ 0) :
      shear π a₃ a₂ a₁ a₀ b₂ b₀ (Y - k * t) t = π (Y + evenValue t) :=
    congrArg π (cancelOdd _ _ _ _ _ _ _ _ _ h₃ h₁ ht)
  have sqNeg (t : F) : (-t)^2 = t^2 := by grind only
  have reflect (t : F) : evenValue (-t) = evenValue t := by
    simp only [evenValue, sqNeg]
  have o := atPoint (3 * s) hout
  have no := atPoint (-(3 * s)) (by rwa [sqNeg])
  have i := atPoint s hin
  have ni := atPoint (-s) (by rwa [sqNeg])
  rw [reflect] at no ni
  have center : Y + evenValue (3 * s) = outer := by dsimp [Y]; grind only
  rw [center] at no o
  refine ⟨Y - k * (-(3 * s)), -(3 * s), -(2 * k * s), 2 * s, hstep, no, ?_, ?_⟩
  · rw [show Y - k * -(3*s) + -(2*k*s) = Y - k * (-s) by grind only,
        show -(3*s) + 2*s = -s by grind only,
        show Y - k * -(3*s) + 2 * -(2*k*s) = Y - k*s by grind only,
        show -(3*s) + 2 * (2*s) = s by grind only]
    exact ni.trans i.symm
  · rw [show Y - k * -(3*s) + 3 * -(2*k*s) = Y - k*(3*s) by grind only,
        show -(3*s) + 3 * (2*s) = 3*s by grind only]
    exact o

end PathWeaverFormal.QuadraticDenominator
