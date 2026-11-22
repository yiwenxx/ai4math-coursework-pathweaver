/-
PathWeaverFormal.WvcDuality
Pure Lean 4 formalization of Weighted Vertex Cover weak LP duality
and exact optimality certification via integer edge-packing duals.
-/

namespace PathWeaverFormal.Wvc

def sumNat (n : Nat) (f : Nat → Nat) : Nat :=
  match n with
  | 0 => 0
  | k + 1 => sumNat k f + f k

theorem sumNat_eq_zero {n : Nat} {f : Nat → Nat} (h : ∀ i, i < n → f i = 0) :
    sumNat n f = 0 := by
  induction n with
  | zero => rfl
  | succ k ih =>
      simp only [sumNat]
      have hk := h k (Nat.lt_succ_self k)
      have hprev := ih (fun i hi => h i (Nat.lt_trans hi (Nat.lt_succ_self k)))
      omega

theorem sumNat_add (n : Nat) (f g : Nat → Nat) :
    sumNat n (fun i => f i + g i) = sumNat n f + sumNat n g := by
  induction n with
  | zero => rfl
  | succ k ih =>
      simp only [sumNat, ih]
      omega

theorem sumNat_mono {n : Nat} {f g : Nat → Nat}
    (h : ∀ i, i < n → f i ≤ g i) :
    sumNat n f ≤ sumNat n g := by
  induction n with
  | zero => exact Nat.le_refl 0
  | succ k ih =>
      have hk := h k (Nat.lt_succ_self k)
      have hprev := ih (fun i hi => h i (Nat.lt_trans hi (Nat.lt_succ_self k)))
      simp only [sumNat]
      omega

theorem sumNat_single {n target : Nat} (ht : target < n) (val : Nat) :
    sumNat n (fun i => if i = target then val else 0) = val := by
  induction n with
  | zero => omega
  | succ k ih =>
      simp only [sumNat]
      by_cases heq : k = target
      · subst heq
        have hz : sumNat k (fun i => if i = k then val else 0) = 0 := by
          apply sumNat_eq_zero
          intro i hi
          simp [Nat.ne_of_lt hi]
        simp [hz]
      · have hlt : target < k := by omega
        have hprev := ih hlt
        simp [hprev, heq]

def IsValidCover (edges : List (Nat × Nat)) (sel : Nat → Bool) : Prop :=
  ∀ e ∈ edges, sel e.1 = true ∨ sel e.2 = true

def ValidEdges (numVertices : Nat) (edges : List (Nat × Nat)) : Prop :=
  ∀ e ∈ edges, e.1 < numVertices ∧ e.2 < numVertices ∧ e.1 ≠ e.2

def incidentDualSum (v : Nat) : List (Nat × Nat) → List Nat → Nat
  | [], _ => 0
  | _, [] => 0
  | (a, b) :: es, y :: ys =>
      (if a == v || b == v then y else 0) + incidentDualSum v es ys

def sumList : List Nat → Nat
  | [] => 0
  | x :: xs => x + sumList xs

def coverWeight (numVertices : Nat) (weights : Nat → Nat) (sel : Nat → Bool) : Nat :=
  sumNat numVertices (fun v => if sel v then weights v else 0)

theorem sum_incident_cover_ge (numVertices : Nat)
    (edges : List (Nat × Nat)) (duals : List Nat) (sel : Nat → Bool)
    (hlen : edges.length = duals.length)
    (hvalid : ValidEdges numVertices edges)
    (hcover : IsValidCover edges sel) :
    sumList duals ≤ sumNat numVertices (fun v => if sel v then incidentDualSum v edges duals else 0) := by
  induction edges generalizing duals with
  | nil =>
      cases duals with
      | nil => simp [sumList]
      | cons => simp at hlen
  | cons e es ih =>
      cases duals with
      | nil => simp at hlen
      | cons y ys =>
          have hlen' : es.length = ys.length := by simpa using hlen
          have hedge := hvalid e (List.mem_cons_self)
          have hcov_e := hcover e (List.mem_cons_self)
          have hvalid_es : ValidEdges numVertices es :=
            fun x hx => hvalid x (List.mem_cons_of_mem e hx)
          have hcov_es : IsValidCover es sel :=
            fun x hx => hcover x (List.mem_cons_of_mem e hx)
          have ih_rest := ih ys hlen' hvalid_es hcov_es
          rcases e with ⟨a, b⟩
          have ha : a < numVertices := hedge.1
          have hb : b < numVertices := hedge.2.1
          have hne : a ≠ b := hedge.2.2
          have hsplit :
              sumNat numVertices (fun v => if sel v then incidentDualSum v ((a, b) :: es) (y :: ys) else 0) =
              sumNat numVertices (fun v => if sel v then (if a == v || b == v then y else 0) else 0) +
              sumNat numVertices (fun v => if sel v then incidentDualSum v es ys else 0) := by
            rw [← sumNat_add]
            congr 1
            funext v
            by_cases hs : sel v = true
            · simp [hs, incidentDualSum]
            · simp [hs]
          have hpair :
              sumNat numVertices (fun v => if sel v then (if a == v || b == v then y else 0) else 0) ≥ y := by
            have hdecomp :
                sumNat numVertices (fun v => if sel v then (if a == v || b == v then y else 0) else 0) =
                sumNat numVertices (fun v => if v = a then (if sel a then y else 0) else 0) +
                sumNat numVertices (fun v => if v = b then (if sel b then y else 0) else 0) := by
              rw [← sumNat_add]
              congr 1
              funext v
              by_cases hva : v = a
              · subst hva
                simp [hne]
              · by_cases hvb : v = b
                · subst hvb
                  simp [hva]
                · have h1 : (a == v) = false := beq_false_of_ne (Ne.symm hva)
                  have h2 : (b == v) = false := beq_false_of_ne (Ne.symm hvb)
                  simp [hva, hvb, h1, h2]
            rw [hdecomp, sumNat_single ha, sumNat_single hb]
            rcases hcov_e with h1 | h2
            · simp only [IsValidCover] at *
              have : sel a = true := h1
              simp [this]
            · have : sel b = true := h2
              simp [this]
          rw [hsplit]
          simp only [sumList]
          omega

theorem wvc_weak_duality (numVertices : Nat)
    (weights : Nat → Nat) (edges : List (Nat × Nat)) (duals : List Nat) (sel : Nat → Bool)
    (hlen : edges.length = duals.length)
    (hvalid : ValidEdges numVertices edges)
    (hpack : ∀ v, v < numVertices → incidentDualSum v edges duals ≤ weights v)
    (hcover : IsValidCover edges sel) :
    sumList duals ≤ coverWeight numVertices weights sel := by
  have h1 := sum_incident_cover_ge numVertices edges duals sel hlen hvalid hcover
  have h2 :
      sumNat numVertices (fun v => if sel v then incidentDualSum v edges duals else 0) ≤
      coverWeight numVertices weights sel := by
    apply sumNat_mono
    intro v hv
    by_cases hs : sel v = true
    · simp only [hs, ↓reduceIte]
      exact hpack v hv
    · simp [hs]
  omega

theorem wvc_optimal_from_duality (numVertices : Nat)
    (weights : Nat → Nat) (edges : List (Nat × Nat)) (duals : List Nat) (sel : Nat → Bool)
    (hlen : edges.length = duals.length)
    (hvalid : ValidEdges numVertices edges)
    (hpack : ∀ v, v < numVertices → incidentDualSum v edges duals ≤ weights v)
    (heq : coverWeight numVertices weights sel = sumList duals) :
    ∀ sel', IsValidCover edges sel' → coverWeight numVertices weights sel ≤ coverWeight numVertices weights sel' := by
  intro sel' hcov'
  have hlb := wvc_weak_duality numVertices weights edges duals sel' hlen hvalid hpack hcov'
  omega

-- Decidable finite certificate checkers for exported WVC instances
def getNat (arr : Array Nat) (i : Nat) : Nat :=
  if h : i < arr.size then arr[i] else 0

def getBool (arr : Array Bool) (i : Nat) : Bool :=
  if h : i < arr.size then arr[i] else false

def checkValidEdgesBool (numVertices : Nat) (edges : List (Nat × Nat)) : Bool :=
  edges.all (fun (a, b) => decide (a < numVertices) && decide (b < numVertices) && decide (a != b))

theorem checkValidEdgesBool_sound (numVertices : Nat) (edges : List (Nat × Nat))
    (h : checkValidEdgesBool numVertices edges = true) :
    ValidEdges numVertices edges := by
  unfold checkValidEdgesBool at h
  rw [List.all_eq_true] at h
  intro e he
  have hmem := h e he
  simp only [Bool.and_eq_true, decide_eq_true_eq, bne_iff_ne] at hmem
  exact ⟨hmem.1.1, hmem.1.2, hmem.2⟩

def checkCoverBool (edges : List (Nat × Nat)) (sel : Array Bool) : Bool :=
  edges.all (fun (a, b) => getBool sel a || getBool sel b)

theorem checkCoverBool_sound (edges : List (Nat × Nat)) (sel : Array Bool)
    (h : checkCoverBool edges sel = true) :
    IsValidCover edges (getBool sel) := by
  unfold checkCoverBool at h
  rw [List.all_eq_true] at h
  intro e he
  have hmem := h e he
  simp only [Bool.or_eq_true] at hmem
  exact hmem

def checkPackingLoop (weights : Array Nat) (edges : List (Nat × Nat)) (duals : List Nat) : Nat → Bool
  | 0 => true
  | v + 1 =>
      decide (incidentDualSum v edges duals ≤ getNat weights v) && checkPackingLoop weights edges duals v

theorem checkPackingLoop_sound (weights : Array Nat) (edges : List (Nat × Nat)) (duals : List Nat) (k : Nat)
    (h : checkPackingLoop weights edges duals k = true) :
    ∀ v, v < k → incidentDualSum v edges duals ≤ getNat weights v := by
  induction k with
  | zero =>
      intro v hv
      omega
  | succ k ih =>
      unfold checkPackingLoop at h
      simp only [Bool.and_eq_true, decide_eq_true_eq] at h
      intro v hv
      by_cases hlt : v < k
      · exact ih h.2 v hlt
      · have heq : v = k := by omega
        subst heq
        exact h.1

theorem verify_wvc_dual_bound_sound
    (weights : Array Nat) (edges : List (Nat × Nat)) (duals : List Nat) (sel : Array Bool)
    (hlen : (edges.length == duals.length) = true)
    (hedges : checkValidEdgesBool weights.size edges = true)
    (hpack : checkPackingLoop weights edges duals weights.size = true)
    (hcov : checkCoverBool edges sel = true) :
    IsValidCover edges (getBool sel) ∧
    (∀ sel', IsValidCover edges sel' → sumList duals ≤ coverWeight weights.size (getNat weights) sel') ∧
    sumList duals ≤ coverWeight weights.size (getNat weights) (getBool sel) := by
  have hlen' : edges.length = duals.length := beq_iff_eq.mp hlen
  have hedges' := checkValidEdgesBool_sound weights.size edges hedges
  have hpack' := checkPackingLoop_sound weights edges duals weights.size hpack
  have hcov' := checkCoverBool_sound edges sel hcov
  refine ⟨hcov', ?_, ?_⟩
  · intro sel' hcov_sel'
    exact wvc_weak_duality weights.size (getNat weights) edges duals sel' hlen' hedges' hpack' hcov_sel'
  · exact wvc_weak_duality weights.size (getNat weights) edges duals (getBool sel) hlen' hedges' hpack' hcov'

theorem verify_wvc_optimal_sound
    (weights : Array Nat) (edges : List (Nat × Nat)) (duals : List Nat) (sel : Array Bool)
    (hlen : (edges.length == duals.length) = true)
    (hedges : checkValidEdgesBool weights.size edges = true)
    (hpack : checkPackingLoop weights edges duals weights.size = true)
    (hcov : checkCoverBool edges sel = true)
    (heq : (coverWeight weights.size (getNat weights) (getBool sel) == sumList duals) = true) :
    IsValidCover edges (getBool sel) ∧
    (∀ sel', IsValidCover edges sel' →
      coverWeight weights.size (getNat weights) (getBool sel) ≤
      coverWeight weights.size (getNat weights) sel') := by
  have hlen' : edges.length = duals.length := beq_iff_eq.mp hlen
  have hedges' := checkValidEdgesBool_sound weights.size edges hedges
  have hpack' := checkPackingLoop_sound weights edges duals weights.size hpack
  have hcov' := checkCoverBool_sound edges sel hcov
  have heq' : coverWeight weights.size (getNat weights) (getBool sel) = sumList duals := beq_iff_eq.mp heq
  exact ⟨hcov', wvc_optimal_from_duality weights.size (getNat weights) edges duals (getBool sel) hlen' hedges' hpack' heq'⟩

end PathWeaverFormal.Wvc
