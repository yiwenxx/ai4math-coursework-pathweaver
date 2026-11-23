import PathWeaverFormal.Jsp158Coloring

/-! The first interval on which legality forces a rainbow four-term progression.
The search gives one branch to each existing color and one to a new color.
Completeness uses only the equality pattern of a prefix, for any color type. -/
namespace PathWeaverFormal.Jsp158.ForcedRainbow

abbrev Three {α : Type u} (a b c d : α) : Prop :=
  (a ≠ b ∧ a ≠ c ∧ b ≠ c) ∨ (a ≠ b ∧ a ≠ d ∧ b ≠ d) ∨
  (a ≠ c ∧ a ≠ d ∧ c ≠ d) ∨ (b ≠ c ∧ b ≠ d ∧ c ≠ d)

abbrev Four {α : Type u} (a b c d : α) : Prop :=
  a ≠ b ∧ a ≠ c ∧ a ≠ d ∧ b ≠ c ∧ b ≠ d ∧ c ≠ d

def Legal {α : Type u} (n : Nat) (f : Nat → α) : Prop :=
  ∀ a d, 0 < d → a + 3*d < n →
    Three (f a) (f (a+d)) (f (a+2*d)) (f (a+3*d))

def HasRainbow {α : Type u} (n : Nat) (f : Nat → α) : Prop :=
  ∃ a d, 0 < d ∧ a + 3*d < n ∧ Four (f a) (f (a+d)) (f (a+2*d)) (f (a+3*d))

private def put (w : Nat → Nat) (n c i : Nat) := if i = n then c else w i

private def agrees {α : Type u} (f : Nat → α) (w : Nat → Nat) (n : Nat) :=
  ∀ i j, i < n → j < n → (w i = w j ↔ f i = f j)

private theorem nextLabel {α : Type u} {f : Nat → α} {w : Nat → Nat} {n used : Nat}
    (sig : agrees f w n) (bounds : ∀ i, i < n → w i < used) :
    ∃ c, c ≤ used ∧ agrees f (put w n c) (n+1) ∧
      ∀ i, i < n+1 → put w n c i < max used (c+1) := by
  have choose : ∃ c, c ≤ used ∧ ∀ i, i < n → (c = w i ↔ f n = f i) := by
    by_cases old : ∃ j, j < n ∧ f n = f j
    · obtain ⟨j,hj,eq⟩ := old
      exact ⟨w j, Nat.le_of_lt (bounds _ hj), fun i hi => eq ▸ sig j i hj hi⟩
    · refine ⟨used, Nat.le_refl _, fun i hi => ?_⟩
      exact ⟨fun h => False.elim (Nat.ne_of_lt (bounds i hi) h.symm),
        fun h => False.elim (old ⟨i,hi,h⟩)⟩
  obtain ⟨c,hc,rel⟩ := choose
  refine ⟨c,hc,?_,?_⟩
  · intro i j hi hj
    by_cases ei : i = n <;> by_cases ej : j = n
    · simp [ei,ej]
    · simpa [put,ei,ej] using rel j (by omega)
    · simpa [put,ei,ej,eq_comm] using rel i (by omega)
    · simpa [put,ei,ej] using sig i j (by omega) (by omega)
  · intro i hi
    by_cases e : i = n
    · simpa [put,e] using Nat.lt_of_lt_of_le (Nat.lt_succ_self c) (Nat.le_max_right used (c+1))
    · simp only [put,ite_eq_right e]
      exact Nat.lt_of_lt_of_le (bounds i (by omega)) (Nat.le_max_left ..)

private def lastOK (n : Nat) (w : Nat → Nat) : Bool :=
  (List.range (n/3+1)).all fun d =>
    let a := n-3*d
    d == 0 || decide (Three (w a) (w (a+d)) (w (a+2*d)) (w (a+3*d)) ∧
                     ¬ Four (w a) (w (a+d)) (w (a+2*d)) (w (a+3*d)))

private theorem lastOK_of {α : Type u} {N n : Nat} {f : Nat → α} {w : Nat → Nat}
    (inside : n < N) (sig : agrees f w (n+1)) (legal : Legal N f)
    (absent : ¬HasRainbow N f) : lastOK n w = true := by
  apply List.all_eq_true.mpr
  intro d hd
  have bound := List.mem_range.mp hd
  by_cases zero : d = 0
  · simp [zero]
  · let a := n-3*d
    have eq : a+3*d = n := by dsimp [a]; omega
    have h0 : a < n+1 := by omega
    have h1 : a+d < n+1 := by omega
    have h2 : a+2*d < n+1 := by omega
    have h3 : a+3*d < n+1 := by omega
    have pos : 0 < d := by omega
    have hr : ¬ Four (f a) (f (a+d)) (f (a+2*d)) (f (a+3*d)) :=
      fun r => absent ⟨a,d,pos,by omega,r⟩
    have ok := And.intro (legal a d pos (by omega)) hr
    change (d == 0 || decide (Three (w a) (w (a+d)) (w (a+2*d)) (w (a+3*d)) ∧
                              ¬ Four (w a) (w (a+d)) (w (a+2*d)) (w (a+3*d)))) = true
    simpa only [beq_iff_eq, Bool.or_eq_true, decide_eq_true_eq, zero, false_or,
      Three, Four, ne_eq, sig _ _ h0 h1, sig _ _ h0 h2, sig _ _ h0 h3,
      sig _ _ h1 h2, sig _ _ h1 h3, sig _ _ h2 h3] using ok

private def survives : Nat → Nat → Nat → (Nat → Nat) → Bool
  | 0, _, _, _ => true
  | k+1, n, used, w => (List.range (used+1)).any fun c =>
      let v := put w n c
      lastOK n v && survives k (n+1) (max used (c+1)) v

private theorem complete {α : Type u} {N : Nat} {f : Nat → α}
    (legal : Legal N f) (absent : ¬HasRainbow N f)
    (k n used : Nat) (w : Nat → Nat) (size : n+k = N)
    (sig : agrees f w n) (bounds : ∀ i, i<n → w i<used) :
    survives k n used w = true := by
  induction k generalizing n used w with
  | zero => rfl
  | succ k ih =>
    obtain ⟨c,hc,hs,hb⟩ := nextLabel sig bounds
    apply List.any_eq_true.mpr
    refine ⟨c, List.mem_range.mpr (by omega), ?_⟩
    simp only [Bool.and_eq_true]
    constructor
    · exact lastOK_of (by omega) hs legal absent
    · exact ih _ _ _ (by omega) hs hb

set_option maxRecDepth 16000
set_option maxHeartbeats 8000000

private theorem exhausted : survives 19 0 0 (fun _ => 0) = false := by decide +kernel

/-- No bound on the size of the palette and no decidable equality on it are assumed. -/
theorem forces19 {α : Type u} (f : Nat → α) (legal : Legal 19 f) : HasRainbow 19 f := by
  apply Classical.byContradiction
  intro absent
  have h := complete legal absent 19 0 0 (fun _ => 0) rfl
    (by intro i j hi; omega) (by intro i hi; omega)
  rw [exhausted] at h
  contradiction

def witness18 : Array Nat := #[0,0,1,2,1,3,3,0,2,3,3,1,0,1,2,2,0,4]

theorem witness18_exact : witness18.size = 18 ∧ IsFourAPFree3 witness18 ∧
    ¬ HasRainbow 18 (getColor witness18) := by
  refine ⟨rfl, checkFourAPFree3_sound _ (by decide +kernel), ?_⟩
  have table : ∀ a d : Fin 18, 0 < d.val → a.val + 3*d.val < 18 →
      ¬ Four (getColor witness18 a.val) (getColor witness18 (a.val+d.val))
        (getColor witness18 (a.val+2*d.val)) (getColor witness18 (a.val+3*d.val)) := by
    decide +kernel
  rintro ⟨a,d,hd,ha,h⟩
  exact table ⟨a,by omega⟩ ⟨d,by omega⟩ hd ha h

/-- The sharp threshold for an interval of arbitrary natural length. -/
theorem threshold (n : Nat) :
    (∀ f : Nat → Nat, Legal n f → HasRainbow n f) ↔ 19 ≤ n := by
  constructor
  · intro h
    apply Classical.byContradiction
    intro short
    have good : Legal n (getColor witness18) := by
      intro a d hd ha
      exact witness18_exact.2.1 a d hd (by rw [witness18_exact.1]; omega)
    obtain ⟨a,d,hd,ha,hap⟩ := h _ good
    exact witness18_exact.2.2 ⟨a,d,hd,by omega,hap⟩
  · intro big f legal
    obtain ⟨a,d,hd,ha,hap⟩ := forces19 f (fun a d hd ha => legal a d hd (by omega))
    exact ⟨a,d,hd,by omega,hap⟩

#print axioms forces19
#print axioms threshold

end PathWeaverFormal.Jsp158.ForcedRainbow
