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

/-!
## Cyclic ABBA-Free Template Verification
A cyclic template `colors` on `Z / m Z` (`m = colors.size`) is ABBA-free if for every
start `a < m` and nonzero step `0 < d < m`, we do not simultaneously have
`c(a) = c((a + 3d) % m)` and `c((a + d) % m) = c((a + 2d) % m)`.
-/

def NotABBA (c0 c1 c2 c3 : Nat) : Prop :=
  c0 ≠ c3 ∨ c1 ≠ c2

def checkNotABBA (c0 c1 c2 c3 : Nat) : Bool :=
  (c0 != c3) || (c1 != c2)

theorem checkNotABBA_sound {c0 c1 c2 c3 : Nat}
    (h : checkNotABBA c0 c1 c2 c3 = true) :
    NotABBA c0 c1 c2 c3 := by
  unfold checkNotABBA at h
  unfold NotABBA
  simp only [Bool.or_eq_true, bne_iff_ne] at h
  exact h

def IsCyclicABBAFree (colors : Array Nat) : Prop :=
  ∀ a d : Nat, a < colors.size → 0 < d → d < colors.size →
    NotABBA
      (getColor colors a)
      (getColor colors ((a + d) % colors.size))
      (getColor colors ((a + 2 * d) % colors.size))
      (getColor colors ((a + 3 * d) % colors.size))

def checkCyclicStarts (colors : Array Nat) (d : Nat) : Nat → Bool
  | 0 => true
  | a + 1 =>
      let m := colors.size
      let ok :=
        checkNotABBA
          (getColor colors a)
          (getColor colors ((a + d) % m))
          (getColor colors ((a + 2 * d) % m))
          (getColor colors ((a + 3 * d) % m))
      ok && checkCyclicStarts colors d a

theorem checkCyclicStarts_sound (colors : Array Nat) (d k : Nat)
    (h : checkCyclicStarts colors d k = true) :
    ∀ a : Nat, a < k →
      NotABBA
        (getColor colors a)
        (getColor colors ((a + d) % colors.size))
        (getColor colors ((a + 2 * d) % colors.size))
        (getColor colors ((a + 3 * d) % colors.size)) := by
  induction k with
  | zero =>
      intro a ha
      omega
  | succ k ih =>
      unfold checkCyclicStarts at h
      simp only [Bool.and_eq_true] at h
      intro a ha
      by_cases hlt : a < k
      · exact ih h.2 a hlt
      · have heq : a = k := by omega
        subst heq
        exact checkNotABBA_sound h.1

def checkCyclicSteps (colors : Array Nat) : Nat → Bool
  | 0 => true
  | d + 1 =>
      let ok := checkCyclicStarts colors (d + 1) colors.size
      ok && checkCyclicSteps colors d

theorem checkCyclicSteps_sound (colors : Array Nat) (maxD : Nat)
    (h : checkCyclicSteps colors maxD = true) :
    ∀ a d : Nat, a < colors.size → 0 < d → d ≤ maxD →
      NotABBA
        (getColor colors a)
        (getColor colors ((a + d) % colors.size))
        (getColor colors ((a + 2 * d) % colors.size))
        (getColor colors ((a + 3 * d) % colors.size)) := by
  induction maxD with
  | zero =>
      intro a d _ hd hle
      omega
  | succ maxD ih =>
      unfold checkCyclicSteps at h
      simp only [Bool.and_eq_true] at h
      intro a d ha hd hle
      by_cases hlt : d ≤ maxD
      · exact ih h.2 a d ha hd hlt
      · have heq : d = maxD + 1 := by omega
        subst heq
        exact checkCyclicStarts_sound colors (maxD + 1) colors.size h.1 a ha

def checkCyclicABBAFree (colors : Array Nat) : Bool :=
  if colors.size ≤ 1 then
    true
  else
    checkCyclicSteps colors (colors.size - 1)

theorem checkCyclicABBAFree_sound (colors : Array Nat)
    (h : checkCyclicABBAFree colors = true) :
    IsCyclicABBAFree colors := by
  unfold checkCyclicABBAFree at h
  intro a d ha hd hd_lt
  have hgt : ¬ colors.size ≤ 1 := by omega
  simp only [hgt, ↓reduceIte] at h
  have hd_le : d ≤ colors.size - 1 := by omega
  exact checkCyclicSteps_sound colors (colors.size - 1) h a d ha hd hd_le

def AllColorsBelow (colors : Array Nat) (r : Nat) : Prop :=
  ∀ i : Nat, i < colors.size → getColor colors i < r

def checkColorsBelowPrefix (colors : Array Nat) (r : Nat) : Nat → Bool
  | 0 => true
  | i + 1 => (getColor colors i < r) && checkColorsBelowPrefix colors r i

theorem checkColorsBelowPrefix_sound (colors : Array Nat) (r k : Nat)
    (h : checkColorsBelowPrefix colors r k = true) :
    ∀ i : Nat, i < k → getColor colors i < r := by
  induction k with
  | zero =>
      intro i hi
      omega
  | succ k ih =>
      unfold checkColorsBelowPrefix at h
      simp only [Bool.and_eq_true, decide_eq_true_eq] at h
      intro i hi
      by_cases hlt : i < k
      · exact ih h.2 i hlt
      · have heq : i = k := by omega
        subst heq
        exact h.1

def checkColorsBelow (colors : Array Nat) (r : Nat) : Bool :=
  checkColorsBelowPrefix colors r colors.size

theorem checkColorsBelow_sound (colors : Array Nat) (r : Nat)
    (h : checkColorsBelow colors r = true) :
    AllColorsBelow colors r := by
  unfold checkColorsBelow at h
  intro i hi
  exact checkColorsBelowPrefix_sound colors r colors.size h i hi

end PathWeaverFormal.Jsp158
