/-
PathWeaverFormal.EdaDuality
Pure Lean 4 formalization of capacity-1 assignment duality
for the EDA relaxed path-bound matching subproblem.
-/

namespace PathWeaverFormal.Eda

def sumInt (n : Nat) (f : Nat → Int) : Int :=
  match n with
  | 0 => 0
  | k + 1 => sumInt k f + f k

theorem sumInt_congr {n : Nat} {f g : Nat → Int}
    (h : ∀ i, i < n → f i = g i) :
    sumInt n f = sumInt n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
      have hk := h k (Nat.lt_succ_self k)
      have hprev := ih (fun i hi => h i (Nat.lt_trans hi (Nat.lt_succ_self k)))
      simp only [sumInt, hprev, hk]

theorem sumInt_add (n : Nat) (f g : Nat → Int) :
    sumInt n (fun i => f i + g i) = sumInt n f + sumInt n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
      simp only [sumInt, ih]
      omega

theorem sumInt_mono {n : Nat} {f g : Nat → Int}
    (h : ∀ i, i < n → f i ≤ g i) :
    sumInt n f ≤ sumInt n g := by
  induction n with
  | zero => exact Int.le_refl 0
  | succ k ih =>
      have hk := h k (Nat.lt_succ_self k)
      have hprev := ih (fun i hi => h i (Nat.lt_trans hi (Nat.lt_succ_self k)))
      simp only [sumInt]
      omega

theorem sumInt_nonpos {n : Nat} {f : Nat → Int}
    (h : ∀ i, i < n → f i ≤ 0) :
    sumInt n f ≤ 0 := by
  induction n with
  | zero => exact Int.le_refl 0
  | succ k ih =>
      have hk := h k (Nat.lt_succ_self k)
      have hprev := ih (fun i hi => h i (Nat.lt_trans hi (Nat.lt_succ_self k)))
      simp only [sumInt]
      omega

def IsFeasibleMatching (n m : Nat) (allowed : Nat → Nat → Bool) (assign : Nat → Nat) : Prop :=
  (∀ e, e < n → assign e < m ∧ allowed e (assign e) = true) ∧
  (∀ e1 e2, e1 < n → e2 < n → assign e1 = assign e2 → e1 = e2)

def siteUsedBelow (k : Nat) (assign : Nat → Nat) (s : Nat) : Bool :=
  match k with
  | 0 => false
  | p + 1 => siteUsedBelow p assign s || (assign p == s)

theorem siteUsedBelow_false_of_fresh {k : Nat} {assign : Nat → Nat}
    (hinj : ∀ e1 e2, e1 < k + 1 → e2 < k + 1 → assign e1 = assign e2 → e1 = e2) :
    siteUsedBelow k assign (assign k) = false := by
  have hne : ∀ p, p ≤ k → (∀ e, e < p → assign e ≠ assign k) → siteUsedBelow p assign (assign k) = false := by
    intro p hp hall
    induction p with
    | zero => rfl
    | succ q ih =>
        have hprev := ih (by omega) (fun e he => hall e (by omega))
        have hq : assign q ≠ assign k := hall q (Nat.lt_succ_self q)
        have hq_bool : (assign q == assign k) = false := beq_false_of_ne hq
        simp [siteUsedBelow, hprev, hq_bool]
  apply hne k (Nat.le_refl k)
  intro e he heq
  have hsame := hinj e k (by omega) (Nat.lt_succ_self k) heq
  omega

def remPotential (k : Nat) (assign : Nat → Nat) (v : Nat → Int) (s : Nat) : Int :=
  if siteUsedBelow k assign s then 0 else v s

theorem sumInt_step_assign (m k : Nat) (assign : Nat → Nat) (v : Nat → Int)
    (hs : assign k < m)
    (hfresh : siteUsedBelow k assign (assign k) = false) :
    sumInt m (remPotential (k + 1) assign v) + v (assign k) =
    sumInt m (remPotential k assign v) := by
  induction m with
  | zero => omega
  | succ p ih =>
      simp only [sumInt]
      by_cases hp : assign k = p
      · have hprev : sumInt p (remPotential (k + 1) assign v) = sumInt p (remPotential k assign v) := by
          apply sumInt_congr
          intro s hs_lt
          have hne : assign k ≠ s := by omega
          have hbool : (assign k == s) = false := beq_false_of_ne hne
          simp [remPotential, siteUsedBelow, hbool]
        have hcurr_next : remPotential (k + 1) assign v p = 0 := by
          rw [← hp]
          simp [remPotential, siteUsedBelow]
        have hcurr_prev : remPotential k assign v p = v (assign k) := by
          rw [← hp]
          simp [remPotential, hfresh]
        rw [hprev, hcurr_next, hcurr_prev]
        omega
      · have hlt : assign k < p := by omega
        have hih := ih hlt
        have hbool : (assign k == p) = false := beq_false_of_ne hp
        have htail : remPotential (k + 1) assign v p = remPotential k assign v p := by
          simp [remPotential, siteUsedBelow, hbool]
        rw [htail]
        omega

theorem sumInt_assign_ge_potential (n m : Nat) (assign : Nat → Nat) (v : Nat → Int)
    (hbounds : ∀ e, e < n → assign e < m)
    (hinj : ∀ e1 e2, e1 < n → e2 < n → assign e1 = assign e2 → e1 = e2)
    (hnonpos : ∀ s, s < m → v s ≤ 0) :
    sumInt m v ≤ sumInt n (fun e => v (assign e)) := by
  have hinv : ∀ k, k ≤ n →
      sumInt m v = sumInt m (remPotential k assign v) + sumInt k (fun e => v (assign e)) := by
    intro k hk
    induction k with
    | zero =>
        simp only [sumInt]
        have hz : sumInt m (remPotential 0 assign v) = sumInt m v := by
          apply sumInt_congr
          intro s _
          rfl
        omega
    | succ q ih =>
        have hq := ih (by omega)
        have hsq : assign q < m := hbounds q (by omega)
        have hinj_q : ∀ e1 e2, e1 < q + 1 → e2 < q + 1 → assign e1 = assign e2 → e1 = e2 :=
          fun e1 e2 h1 h2 => hinj e1 e2 (by omega) (by omega)
        have hfresh := siteUsedBelow_false_of_fresh hinj_q
        have hstep := sumInt_step_assign m q assign v hsq hfresh
        simp only [sumInt]
        omega
  have hfinal := hinv n (Nat.le_refl n)
  have hrem_nonpos : sumInt m (remPotential n assign v) ≤ 0 := by
    apply sumInt_nonpos
    intro s hs
    unfold remPotential
    split
    · exact Int.le_refl 0
    · exact hnonpos s hs
  omega

theorem eda_weak_duality (n m : Nat)
    (lengths : Nat → Nat → Int) (allowed : Nat → Nat → Bool)
    (u v : Nat → Int) (assign : Nat → Nat)
    (hfeas : IsFeasibleMatching n m allowed assign)
    (hv : ∀ s, s < m → v s ≤ 0)
    (hdual : ∀ e s, e < n → s < m → allowed e s = true → u e + v s ≤ lengths e s) :
    sumInt n u + sumInt m v ≤ sumInt n (fun e => lengths e (assign e)) := by
  have hbounds : ∀ e, e < n → assign e < m := fun e he => (hfeas.1 e he).1
  have hv_le := sumInt_assign_ge_potential n m assign v hbounds hfeas.2 hv
  have hpair : sumInt n (fun e => u e + v (assign e)) ≤ sumInt n (fun e => lengths e (assign e)) := by
    apply sumInt_mono
    intro e he
    have hall := hfeas.1 e he
    exact hdual e (assign e) he hall.1 hall.2
  rw [sumInt_add] at hpair
  omega

theorem eda_optimal_from_duality (n m : Nat)
    (lengths : Nat → Nat → Int) (allowed : Nat → Nat → Bool)
    (u v : Nat → Int) (assign : Nat → Nat)
    (_hfeas : IsFeasibleMatching n m allowed assign)
    (hv : ∀ s, s < m → v s ≤ 0)
    (hdual : ∀ e s, e < n → s < m → allowed e s = true → u e + v s ≤ lengths e s)
    (heq : sumInt n (fun e => lengths e (assign e)) = sumInt n u + sumInt m v) :
    ∀ assign', IsFeasibleMatching n m allowed assign' →
      sumInt n (fun e => lengths e (assign e)) ≤ sumInt n (fun e => lengths e (assign' e)) := by
  intro assign' hfeas'
  have hlb := eda_weak_duality n m lengths allowed u v assign' hfeas' hv hdual
  omega

-- Decidable witness checkers for exported EDA duality certificates
def getInt (arr : Array Int) (i : Nat) : Int :=
  if h : i < arr.size then arr[i] else 0

def getNat (arr : Array Nat) (i : Nat) : Nat :=
  if h : i < arr.size then arr[i] else 0

def getCellInt (mat : Array (Array Int)) (e s : Nat) : Int :=
  if h1 : e < mat.size then
    let row := mat[e]
    if h2 : s < row.size then row[s] else 0
  else 0

def getCellBool (mat : Array (Array Bool)) (e s : Nat) : Bool :=
  if h1 : e < mat.size then
    let row := mat[e]
    if h2 : s < row.size then row[s] else false
  else false

def checkNonposLoop (v : Array Int) : Nat → Bool
  | 0 => true
  | s + 1 => decide (getInt v s ≤ 0) && checkNonposLoop v s

theorem checkNonposLoop_sound (v : Array Int) (k : Nat)
    (h : checkNonposLoop v k = true) :
    ∀ s, s < k → getInt v s ≤ 0 := by
  induction k with
  | zero => intro s hs; omega
  | succ k ih =>
      unfold checkNonposLoop at h
      simp only [Bool.and_eq_true, decide_eq_true_eq] at h
      intro s hs
      by_cases hlt : s < k
      · exact ih h.2 s hlt
      · have heq : s = k := by omega
        subst heq
        exact h.1

def checkFeasLoop (m : Nat) (allowed : Array (Array Bool)) (assign : Array Nat) : Nat → Bool
  | 0 => true
  | e + 1 =>
      let s := getNat assign e
      decide (s < m) && getCellBool allowed e s && checkFeasLoop m allowed assign e

theorem checkFeasLoop_sound (m : Nat) (allowed : Array (Array Bool)) (assign : Array Nat) (k : Nat)
    (h : checkFeasLoop m allowed assign k = true) :
    ∀ e, e < k → getNat assign e < m ∧ getCellBool allowed e (getNat assign e) = true := by
  induction k with
  | zero => intro e he; omega
  | succ k ih =>
      unfold checkFeasLoop at h
      simp only [Bool.and_eq_true, decide_eq_true_eq] at h
      intro e he
      by_cases hlt : e < k
      · exact ih h.2 e hlt
      · have heq : e = k := by omega
        subst heq
        exact ⟨h.1.1, h.1.2⟩

def checkInjPair (assign : Array Nat) (e1 : Nat) : Nat → Bool
  | 0 => true
  | e2 + 1 => decide (getNat assign e1 ≠ getNat assign e2) && checkInjPair assign e1 e2

theorem checkInjPair_sound (assign : Array Nat) (e1 k : Nat)
    (h : checkInjPair assign e1 k = true) :
    ∀ e2, e2 < k → getNat assign e1 ≠ getNat assign e2 := by
  induction k with
  | zero => intro e2 h2; omega
  | succ k ih =>
      unfold checkInjPair at h
      simp only [Bool.and_eq_true, decide_eq_true_eq] at h
      intro e2 h2
      by_cases hlt : e2 < k
      · exact ih h.2 e2 hlt
      · have heq : e2 = k := by omega
        subst heq
        exact h.1

def checkInjLoop (assign : Array Nat) : Nat → Bool
  | 0 => true
  | e + 1 => checkInjPair assign e e && checkInjLoop assign e

theorem checkInjLoop_sound (assign : Array Nat) (k : Nat)
    (h : checkInjLoop assign k = true) :
    ∀ e1 e2, e1 < k → e2 < k → getNat assign e1 = getNat assign e2 → e1 = e2 := by
  induction k with
  | zero => intro e1 e2 h1; omega
  | succ k ih =>
      unfold checkInjLoop at h
      simp only [Bool.and_eq_true] at h
      intro e1 e2 h1 h2 heq
      by_cases h1k : e1 < k
      · by_cases h2k : e2 < k
        · exact ih h.2 e1 e2 h1k h2k heq
        · have he2 : k = e2 := by omega
          subst he2
          have hne := checkInjPair_sound assign k k h.1 e1 h1k
          exact absurd heq.symm hne
      · have he1 : k = e1 := by omega
        subst he1
        by_cases h2k : e2 < k
        · have hne := checkInjPair_sound assign k k h.1 e2 h2k
          exact absurd heq hne
        · omega

def checkDualRow (lengths : Array (Array Int)) (allowed : Array (Array Bool))
    (u v : Array Int) (e : Nat) : Nat → Bool
  | 0 => true
  | s + 1 =>
      let ok := if getCellBool allowed e s then decide (getInt u e + getInt v s ≤ getCellInt lengths e s) else true
      ok && checkDualRow lengths allowed u v e s

theorem checkDualRow_sound (lengths : Array (Array Int)) (allowed : Array (Array Bool))
    (u v : Array Int) (e m : Nat)
    (h : checkDualRow lengths allowed u v e m = true) :
    ∀ s, s < m → getCellBool allowed e s = true → getInt u e + getInt v s ≤ getCellInt lengths e s := by
  induction m with
  | zero => intro s hs; omega
  | succ m ih =>
      unfold checkDualRow at h
      simp only [Bool.and_eq_true] at h
      intro s hs hall
      by_cases hlt : s < m
      · exact ih h.2 s hlt hall
      · have heq : s = m := by omega
        subst heq
        have h1 := h.1
        simp only [hall, ↓reduceIte, decide_eq_true_eq] at h1
        exact h1

def checkDualLoop (m : Nat) (lengths : Array (Array Int)) (allowed : Array (Array Bool))
    (u v : Array Int) : Nat → Bool
  | 0 => true
  | e + 1 => checkDualRow lengths allowed u v e m && checkDualLoop m lengths allowed u v e

theorem checkDualLoop_sound (m : Nat) (lengths : Array (Array Int)) (allowed : Array (Array Bool))
    (u v : Array Int) (n : Nat)
    (h : checkDualLoop m lengths allowed u v n = true) :
    ∀ e s, e < n → s < m → getCellBool allowed e s = true → getInt u e + getInt v s ≤ getCellInt lengths e s := by
  induction n with
  | zero => intro e s he; omega
  | succ n ih =>
      unfold checkDualLoop at h
      simp only [Bool.and_eq_true] at h
      intro e s he hs hall
      by_cases hlt : e < n
      · exact ih h.2 e s hlt hs hall
      · have heq : n = e := by omega
        subst heq
        exact checkDualRow_sound lengths allowed u v n m h.1 s hs hall

theorem verify_eda_optimal_sound
    (n m : Nat) (lengths : Array (Array Int)) (allowed : Array (Array Bool))
    (u v : Array Int) (assign : Array Nat)
    (hfeas : checkFeasLoop m allowed assign n = true)
    (hinj : checkInjLoop assign n = true)
    (hnonpos : checkNonposLoop v m = true)
    (hdual : checkDualLoop m lengths allowed u v n = true)
    (heq : (sumInt n (fun e => getCellInt lengths e (getNat assign e)) == sumInt n (getInt u) + sumInt m (getInt v)) = true) :
    IsFeasibleMatching n m (getCellBool allowed) (getNat assign) ∧
    (∀ assign', IsFeasibleMatching n m (getCellBool allowed) assign' →
      sumInt n (fun e => getCellInt lengths e (getNat assign e)) ≤
      sumInt n (fun e => getCellInt lengths e (assign' e))) := by
  have hmatching : IsFeasibleMatching n m (getCellBool allowed) (getNat assign) :=
    ⟨checkFeasLoop_sound m allowed assign n hfeas, checkInjLoop_sound assign n hinj⟩
  have hv := checkNonposLoop_sound v m hnonpos
  have hd := checkDualLoop_sound m lengths allowed u v n hdual
  have heq' := beq_iff_eq.mp heq
  exact ⟨hmatching, eda_optimal_from_duality n m (getCellInt lengths) (getCellBool allowed) (getInt u) (getInt v) (getNat assign) hmatching hv hd heq'⟩

-- Hall conflict / Pigeonhole lower bound verification for T* > T_relaxed_lb
theorem no_inj_into_shorter [DecidableEq β] :
    ∀ (A : List α) (B : List β) (f : α → β),
      A.Nodup →
      B.length < A.length →
      (∀ a ∈ A, f a ∈ B) →
      (∀ a1 ∈ A, ∀ a2 ∈ A, f a1 = f a2 → a1 = a2) →
      False
  | [], B, _, _, hlen, _, _ => by simp at hlen
  | a :: xs, B, f, hnodup, hlen, hmem, hinj => by
      have ha_mem : f a ∈ B := hmem a (List.mem_cons_self)
      have hnodup_xs : xs.Nodup := (List.nodup_cons.mp hnodup).2
      have ha_notin : a ∉ xs := (List.nodup_cons.mp hnodup).1
      have hlen_B' : (B.erase (f a)).length + 1 = B.length := by
        have := List.length_erase_of_mem ha_mem
        have hpos : 0 < B.length := List.length_pos_of_mem ha_mem
        omega
      have hlen' : (B.erase (f a)).length < xs.length := by
        simp only [List.length_cons] at hlen
        omega
      have hmem' : ∀ y ∈ xs, f y ∈ B.erase (f a) := by
        intro y hy
        have hy_mem : f y ∈ B := hmem y (List.mem_cons_of_mem a hy)
        have hne_y : y ≠ a := fun h => ha_notin (h ▸ hy)
        have hne_fy : f y ≠ f a := fun heq =>
          hne_y (hinj y (List.mem_cons_of_mem a hy) a List.mem_cons_self heq)
        exact (List.mem_erase_of_ne hne_fy).mpr hy_mem
      have hinj' : ∀ a1 ∈ xs, ∀ a2 ∈ xs, f a1 = f a2 → a1 = a2 :=
        fun a1 h1 a2 h2 => hinj a1 (List.mem_cons_of_mem a h1) a2 (List.mem_cons_of_mem a h2)
      exact no_inj_into_shorter xs (B.erase (f a)) f hnodup_xs hlen' hmem' hinj'

def checkEdgesInNeighborhood (n m : Nat) (allowedBelow : Array (Array Bool))
    (blocking : List Nat) (neighborhood : List Nat) : Bool :=
  blocking.all (fun e =>
    decide (e < n) &&
    (List.range m).all (fun s =>
      if getCellBool allowedBelow e s then neighborhood.contains s else true))

theorem checkEdgesInNeighborhood_sound (n m : Nat) (allowedBelow : Array (Array Bool))
    (blocking : List Nat) (neighborhood : List Nat)
    (h : checkEdgesInNeighborhood n m allowedBelow blocking neighborhood = true) :
    ∀ e ∈ blocking, e < n ∧ ∀ s, s < m → getCellBool allowedBelow e s = true → s ∈ neighborhood := by
  unfold checkEdgesInNeighborhood at h
  rw [List.all_eq_true] at h
  intro e he
  have hmem := h e he
  simp only [Bool.and_eq_true, decide_eq_true_eq] at hmem
  refine ⟨hmem.1, ?_⟩
  intro s hs hall
  have hrange := (List.all_eq_true.mp hmem.2) s (List.mem_range.mpr hs)
  simp only [hall, ↓reduceIte, List.contains_eq_mem, decide_eq_true_eq] at hrange
  exact hrange

theorem verify_eda_hall_conflict_sound
    (n m : Nat) (allowedBelow : Array (Array Bool))
    (blocking : List Nat) (neighborhood : List Nat)
    (hnodup : blocking.Nodup = true)
    (hcard : (neighborhood.length < blocking.length) = true)
    (hcover : checkEdgesInNeighborhood n m allowedBelow blocking neighborhood = true) :
    ¬ ∃ assign', IsFeasibleMatching n m (getCellBool allowedBelow) assign' := by
  rintro ⟨assign', hfeas⟩
  have hcov := checkEdgesInNeighborhood_sound n m allowedBelow blocking neighborhood hcover
  have hmem : ∀ e ∈ blocking, assign' e ∈ neighborhood := by
    intro e he
    have ⟨he_lt, hsub⟩ := hcov e he
    have ⟨hs_lt, hs_all⟩ := hfeas.1 e he_lt
    exact hsub (assign' e) hs_lt hs_all
  have hinj : ∀ e1 ∈ blocking, ∀ e2 ∈ blocking, assign' e1 = assign' e2 → e1 = e2 := by
    intro e1 h1 e2 h2 heq
    exact hfeas.2 e1 e2 (hcov e1 h1).1 (hcov e2 h2).1 heq
  exact no_inj_into_shorter blocking neighborhood assign' (of_decide_eq_true (by simpa using hnodup)) (of_decide_eq_true (by simpa using hcard)) hmem hinj

end PathWeaverFormal.Eda
