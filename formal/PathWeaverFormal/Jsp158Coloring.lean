/-
PathWeaverFormal.Jsp158Coloring
Pure Lean 4 formal specification and decidable kernel-checked verifier
for finite JSP-000158 / Erdos #160 four-term arithmetic progression colorings.
-/

namespace PathWeaverFormal.Jsp158

def getColor (colors : Array Nat) (i : Nat) : Nat :=
  if h : i < colors.size then colors[i] else 0

def AtLeastThreeColors (c0 c1 c2 c3 : Nat) : Prop :=
  (c0 ≠ c1 ∧ c0 ≠ c2 ∧ c1 ≠ c2) ∨
  (c0 ≠ c1 ∧ c0 ≠ c3 ∧ c1 ≠ c3) ∨
  (c0 ≠ c2 ∧ c0 ≠ c3 ∧ c2 ≠ c3) ∨
  (c1 ≠ c2 ∧ c1 ≠ c3 ∧ c2 ≠ c3)

def checkTriple (c0 c1 c2 c3 : Nat) : Bool :=
  (c0 != c1 && c0 != c2 && c1 != c2) ||
  (c0 != c1 && c0 != c3 && c1 != c3) ||
  (c0 != c2 && c0 != c3 && c2 != c3) ||
  (c1 != c2 && c1 != c3 && c2 != c3)

theorem checkTriple_sound {c0 c1 c2 c3 : Nat}
    (h : checkTriple c0 c1 c2 c3 = true) :
    AtLeastThreeColors c0 c1 c2 c3 := by
  unfold checkTriple at h
  unfold AtLeastThreeColors
  simp only [Bool.or_eq_true, Bool.and_eq_true, bne_iff_ne] at h
  rcases h with ((⟨⟨h1, h2⟩, h3⟩ | ⟨⟨h1, h2⟩, h3⟩) | ⟨⟨h1, h2⟩, h3⟩) | ⟨⟨h1, h2⟩, h3⟩
  · exact Or.inl ⟨h1, h2, h3⟩
  · exact Or.inr (Or.inl ⟨h1, h2, h3⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨h1, h2, h3⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨h1, h2, h3⟩))

def IsFourAPFree3 (colors : Array Nat) : Prop :=
  ∀ a d : Nat, 0 < d → a + 3 * d < colors.size →
    AtLeastThreeColors
      (getColor colors a)
      (getColor colors (a + d))
      (getColor colors (a + 2 * d))
      (getColor colors (a + 3 * d))

def checkStarts (colors : Array Nat) (d : Nat) : Nat → Bool
  | 0 => true
  | k + 1 =>
      let a := k
      let ok :=
        checkTriple
          (getColor colors a)
          (getColor colors (a + d))
          (getColor colors (a + 2 * d))
          (getColor colors (a + 3 * d))
      ok && checkStarts colors d k

theorem checkStarts_sound (colors : Array Nat) (d k : Nat)
    (h : checkStarts colors d k = true) :
    ∀ a : Nat, a < k →
      AtLeastThreeColors
        (getColor colors a)
        (getColor colors (a + d))
        (getColor colors (a + 2 * d))
        (getColor colors (a + 3 * d)) := by
  induction k with
  | zero =>
      intro a ha
      omega
  | succ k ih =>
      unfold checkStarts at h
      simp only [Bool.and_eq_true] at h
      intro a ha
      by_cases hlt : a < k
      · exact ih h.2 a hlt
      · have heq : a = k := by omega
        subst heq
        exact checkTriple_sound h.1

def checkSteps (colors : Array Nat) : Nat → Bool
  | 0 => true
  | d + 1 =>
      let ok :=
        if 3 * (d + 1) < colors.size then
          checkStarts colors (d + 1) (colors.size - 3 * (d + 1))
        else
          true
      ok && checkSteps colors d

theorem checkSteps_sound (colors : Array Nat) (m : Nat)
    (h : checkSteps colors m = true) :
    ∀ d : Nat, 0 < d → d ≤ m →
      ∀ a : Nat, a + 3 * d < colors.size →
        AtLeastThreeColors
          (getColor colors a)
          (getColor colors (a + d))
          (getColor colors (a + 2 * d))
          (getColor colors (a + 3 * d)) := by
  induction m with
  | zero =>
      intro d hd hle
      omega
  | succ m ih =>
      unfold checkSteps at h
      simp only [Bool.and_eq_true] at h
      intro d hd hle a ha
      by_cases hlt : d ≤ m
      · exact ih h.2 d hd hlt a ha
      · have heq : d = m + 1 := by omega
        subst heq
        have h3 : 3 * (m + 1) < colors.size := by omega
        have hok := h.1
        simp only [h3, ↓reduceIte] at hok
        exact checkStarts_sound colors (m + 1) (colors.size - 3 * (m + 1)) hok a (by omega)

def checkFourAPFree3 (colors : Array Nat) : Bool :=
  checkSteps colors (colors.size / 3)

theorem checkFourAPFree3_sound (colors : Array Nat)
    (h : checkFourAPFree3 colors = true) :
    IsFourAPFree3 colors := by
  unfold checkFourAPFree3 at h
  intro a d hd ha
  have hd_le : d ≤ colors.size / 3 := by omega
  exact checkSteps_sound colors (colors.size / 3) h d hd hd_le a ha

end PathWeaverFormal.Jsp158
