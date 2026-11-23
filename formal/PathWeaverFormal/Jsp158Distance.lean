/- Weighted hitting bounds and their application to the archived mod-257 ABBA table. -/
namespace PathWeaverFormal.Jsp158Distance

def sumOver (xs : List α) (f : α → Nat) : Nat :=
  match xs with
  | [] => 0
  | x :: rest => f x + sumOver rest f

private theorem sum_mono (xs : List α) (f g : α → Nat)
    (h : ∀ x ∈ xs, f x ≤ g x) : sumOver xs f ≤ sumOver xs g := by
  induction xs with
  | nil => exact Nat.le_refl 0
  | cons x xs ih =>
    exact Nat.add_le_add (h x (by simp)) (ih (fun y hy => h y (by simp [hy])))

private theorem summand_le (f : α → Nat) {v : α} {xs : List α} (h : v ∈ xs) :
    f v ≤ sumOver xs f := by
  induction xs with
  | nil => simp at h
  | cons x xs ih =>
    simp only [List.mem_cons] at h
    rcases h with rfl | h
    · simp [sumOver]
    · exact Nat.le_trans (ih h) (Nat.le_add_left _ _)

private theorem sum_add (xs : List α) (f g : α → Nat) :
    sumOver xs (fun x => f x + g x) = sumOver xs f + sumOver xs g := by
  induction xs with
  | nil => rfl
  | cons x xs ih => simp only [sumOver, ih]; omega

private theorem sum_const (xs : List α) (k : Nat) :
    sumOver xs (fun _ => k) = k * xs.length := by
  induction xs with
  | nil => simp [sumOver]
  | cons x xs ih => simp [sumOver, ih, Nat.mul_succ, Nat.add_comm]

private theorem sum_swap (xs : List α) (ys : List β) (f : α → β → Nat) :
    sumOver xs (fun x => sumOver ys (f x)) =
      sumOver ys (fun y => sumOver xs (fun x => f x y)) := by
  induction xs with
  | nil => simp [sumOver, sum_const]
  | cons x xs ih => simp only [sumOver, ih, sum_add]

/-- Every covered edge contributes its weight to at least one changed vertex.
The cap bounds the sum of all incident weights at each such vertex. -/
theorem weighted_cover_bound (edges : List α) (changed : List β)
    (weight : α → Nat) (incident : α → β → Bool) (cap : Nat)
    (hit : ∀ e ∈ edges, ∃ v ∈ changed, incident e v = true)
    (bounded : ∀ v ∈ changed,
      sumOver edges (fun e => if incident e v then weight e else 0) ≤ cap) :
    sumOver edges weight ≤ cap * changed.length := by
  let charge (e : α) (v : β) := if incident e v then weight e else 0
  calc
    sumOver edges weight ≤ sumOver edges (fun e => sumOver changed (charge e)) := by
      apply sum_mono
      intro e he
      obtain ⟨v, hv, hin⟩ := hit e he
      have term := summand_le (charge e) hv
      simpa only [charge, hin, ↓reduceIte] using term
    _ = sumOver changed (fun v => sumOver edges (fun e => charge e v)) :=
      sum_swap edges changed charge
    _ ≤ sumOver changed (fun _ => cap) := sum_mono _ _ _ bounded
    _ = cap * changed.length := sum_const changed cap

structure WeightedAP where
  start : Nat
  step : Nat
  weight : Nat

/- Literal inputs from results/jsp158_mod257_20261122/distance-packing.json.
The label-byte SHA-256 is d893d16e58e9dfcba35eeceb1fd9ab0d989d31e6445329e23af29360d5910de2.
The proofs below recompute all mathematical properties from these literals. -/
def archivedLabels : Array Nat := #[
  3, 3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 2, 2, 2, 3, 3, 3, 3, 3, 0, 0, 0, 0,
  0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3,
  3, 3, 3, 3, 2, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
  1, 3, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 2, 2, 2,
  2, 2, 3, 3, 3, 2, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1, 2, 1, 1, 1, 0, 0, 0, 3,
  1, 3, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 2, 1, 1, 1, 1, 1, 1, 1, 1,
  1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 0, 3, 1, 1,
  1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
  2, 2, 2, 2, 2, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1,
  1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 3, 3, 3, 2, 3, 2, 2, 2, 2, 2, 2, 3, 3, 3]

def packing : List WeightedAP := [
  ⟨0, 2, 141⟩, ⟨1, 3, 8⟩, ⟨2, 39, 52⟩, ⟨4, 39, 108⟩, ⟨5, 97, 39⟩,
  ⟨8, 109, 98⟩, ⟨10, 2, 32⟩, ⟨10, 32, 190⟩, ⟨15, 1, 143⟩, ⟨19, 48, 71⟩,
  ⟨20, 67, 37⟩, ⟨21, 1, 87⟩, ⟨26, 1, 195⟩, ⟨29, 39, 2⟩, ⟨29, 62, 46⟩,
  ⟨30, 86, 92⟩, ⟨31, 52, 111⟩, ⟨32, 1, 2⟩, ⟨33, 1, 32⟩, ⟨33, 79, 80⟩,
  ⟨33, 101, 38⟩, ⟨34, 2, 222⟩, ⟨35, 2, 170⟩, ⟨36, 1, 2⟩, ⟨38, 1, 1⟩,
  ⟨39, 1, 33⟩, ⟨42, 86, 32⟩, ⟨43, 3, 20⟩, ⟨44, 116, 5⟩, ⟨45, 2, 24⟩,
  ⟨45, 3, 232⟩, ⟨46, 87, 65⟩, ⟨47, 1, 24⟩, ⟨50, 3, 129⟩, ⟨52, 79, 56⟩,
  ⟨52, 100, 23⟩, ⟨53, 22, 69⟩, ⟨53, 98, 34⟩, ⟨54, 1, 24⟩, ⟨55, 1, 103⟩,
  ⟨55, 63, 56⟩, ⟨55, 87, 30⟩, ⟨57, 97, 30⟩, ⟨58, 72, 37⟩, ⟨58, 86, 97⟩,
  ⟨58, 96, 1⟩, ⟨60, 54, 62⟩, ⟨60, 73, 158⟩, ⟨60, 74, 36⟩, ⟨61, 1, 6⟩,
  ⟨61, 73, 61⟩, ⟨63, 1, 150⟩, ⟨65, 47, 70⟩, ⟨66, 54, 62⟩, ⟨67, 1, 115⟩,
  ⟨67, 34, 60⟩, ⟨68, 73, 112⟩, ⟨69, 13, 48⟩, ⟨69, 120, 93⟩, ⟨70, 38, 141⟩,
  ⟨71, 13, 91⟩, ⟨71, 49, 48⟩, ⟨71, 72, 5⟩, ⟨72, 12, 49⟩, ⟨72, 48, 146⟩,
  ⟨73, 6, 38⟩, ⟨73, 10, 53⟩, ⟨73, 92, 114⟩, ⟨74, 1, 15⟩, ⟨75, 86, 90⟩,
  ⟨76, 4, 65⟩, ⟨76, 89, 33⟩, ⟨77, 3, 38⟩, ⟨77, 8, 34⟩, ⟨77, 85, 82⟩,
  ⟨77, 112, 87⟩, ⟨78, 9, 35⟩, ⟨78, 100, 63⟩, ⟨79, 1, 101⟩, ⟨79, 111, 80⟩,
  ⟨84, 1, 51⟩, ⟨85, 1, 133⟩, ⟨88, 109, 57⟩, ⟨90, 24, 32⟩, ⟨90, 74, 22⟩,
  ⟨91, 5, 66⟩, ⟨91, 23, 9⟩, ⟨92, 2, 44⟩, ⟨93, 1, 63⟩, ⟨94, 105, 59⟩,
  ⟨98, 2, 89⟩, ⟨101, 63, 96⟩, ⟨102, 1, 127⟩, ⟨104, 5, 36⟩, ⟨105, 20, 79⟩,
  ⟨107, 11, 64⟩, ⟨107, 20, 84⟩, ⟨107, 21, 84⟩, ⟨109, 2, 173⟩, ⟨110, 13, 92⟩,
  ⟨111, 13, 83⟩, ⟨112, 27, 58⟩, ⟨112, 28, 48⟩, ⟨113, 58, 46⟩, ⟨113, 106, 27⟩,
  ⟨114, 58, 52⟩, ⟨114, 105, 10⟩, ⟨118, 4, 79⟩, ⟨118, 5, 33⟩, ⟨119, 48, 15⟩,
  ⟨119, 76, 84⟩, ⟨121, 76, 81⟩, ⟨121, 80, 4⟩, ⟨122, 36, 29⟩, ⟨122, 37, 148⟩,
  ⟨123, 1, 104⟩, ⟨123, 36, 27⟩, ⟨124, 1, 14⟩, ⟨124, 5, 34⟩, ⟨125, 1, 59⟩,
  ⟨128, 19, 42⟩, ⟨128, 67, 6⟩, ⟨129, 1, 135⟩, ⟨130, 113, 5⟩, ⟨132, 115, 15⟩,
  ⟨134, 63, 33⟩, ⟨135, 45, 67⟩, ⟨135, 58, 13⟩, ⟨136, 1, 164⟩, ⟨140, 1, 144⟩,
  ⟨142, 2, 82⟩, ⟨143, 10, 107⟩, ⟨144, 9, 77⟩, ⟨146, 1, 22⟩, ⟨146, 7, 2⟩,
  ⟨146, 29, 8⟩, ⟨147, 28, 84⟩, ⟨148, 28, 153⟩, ⟨149, 85, 25⟩, ⟨149, 86, 34⟩,
  ⟨150, 84, 125⟩, ⟨151, 34, 27⟩, ⟨151, 47, 52⟩, ⟨151, 67, 47⟩, ⟨152, 66, 51⟩,
  ⟨153, 101, 24⟩, ⟨154, 45, 101⟩, ⟨154, 99, 40⟩, ⟨155, 1, 169⟩, ⟨155, 98, 7⟩,
  ⟨160, 1, 65⟩, ⟨160, 98, 46⟩, ⟨161, 12, 38⟩, ⟨161, 98, 64⟩, ⟨163, 122, 14⟩,
  ⟨164, 19, 105⟩, ⟨164, 92, 33⟩, ⟨166, 86, 155⟩, ⟨170, 5, 65⟩, ⟨171, 1, 48⟩,
  ⟨172, 5, 26⟩, ⟨173, 52, 55⟩, ⟨174, 69, 21⟩, ⟨174, 70, 99⟩, ⟨175, 107, 83⟩,
  ⟨176, 1, 93⟩, ⟨176, 120, 11⟩, ⟨177, 1, 101⟩, ⟨177, 2, 36⟩, ⟨179, 21, 26⟩,
  ⟨180, 65, 24⟩, ⟨181, 96, 164⟩, ⟨182, 6, 95⟩, ⟨182, 19, 24⟩, ⟨182, 20, 6⟩,
  ⟨182, 96, 106⟩, ⟨183, 83, 17⟩, ⟨184, 81, 108⟩, ⟨184, 82, 8⟩, ⟨185, 81, 84⟩,
  ⟨186, 72, 52⟩, ⟨186, 80, 148⟩, ⟨186, 81, 26⟩, ⟨186, 118, 30⟩, ⟨187, 47, 81⟩,
  ⟨187, 60, 38⟩, ⟨188, 86, 76⟩, ⟨188, 113, 85⟩, ⟨190, 1, 176⟩, ⟨192, 18, 73⟩,
  ⟨193, 1, 9⟩, ⟨195, 111, 130⟩, ⟨198, 86, 10⟩, ⟨198, 121, 65⟩, ⟨200, 4, 39⟩,
  ⟨200, 40, 73⟩, ⟨200, 41, 11⟩, ⟨200, 86, 13⟩, ⟨201, 2, 145⟩, ⟨201, 4, 70⟩,
  ⟨202, 11, 4⟩, ⟨202, 40, 12⟩, ⟨203, 39, 27⟩, ⟨204, 8, 21⟩, ⟨204, 38, 35⟩,
  ⟨205, 12, 41⟩, ⟨206, 2, 27⟩, ⟨207, 2, 50⟩, ⟨208, 1, 101⟩, ⟨208, 11, 54⟩,
  ⟨209, 5, 6⟩, ⟨209, 122, 29⟩, ⟨211, 3, 105⟩, ⟨213, 7, 26⟩, ⟨215, 1, 110⟩,
  ⟨215, 50, 19⟩, ⟨215, 60, 61⟩, ⟨219, 4, 110⟩, ⟨221, 1, 88⟩, ⟨222, 2, 100⟩,
  ⟨223, 1, 58⟩, ⟨225, 4, 76⟩, ⟨227, 3, 24⟩, ⟨229, 18, 31⟩, ⟨229, 33, 31⟩,
  ⟨235, 1, 180⟩, ⟨238, 51, 54⟩, ⟨239, 1, 150⟩, ⟨240, 14, 33⟩, ⟨243, 5, 126⟩,
  ⟨243, 38, 56⟩, ⟨243, 123, 48⟩, ⟨245, 9, 100⟩, ⟨245, 37, 81⟩, ⟨246, 29, 53⟩,
  ⟨246, 54, 96⟩, ⟨246, 121, 35⟩, ⟨248, 1, 130⟩, ⟨249, 20, 43⟩, ⟨249, 54, 47⟩,
  ⟨249, 55, 1⟩, ⟨250, 7, 1⟩, ⟨250, 53, 124⟩, ⟨251, 100, 83⟩, ⟨252, 6, 24⟩,
  ⟨252, 19, 9⟩, ⟨252, 67, 23⟩, ⟨252, 112, 22⟩, ⟨253, 118, 56⟩, ⟨254, 67, 66⟩,
  ⟨255, 7, 181⟩, ⟨255, 67, 24⟩, ⟨255, 119, 52⟩, ⟨256, 4, 223⟩]

def archivedColor (v : Nat) : Nat := archivedLabels[v]?.getD 0

def site (e : WeightedAP) (i : Nat) : Nat := (e.start + i * e.step) % 257

def touches (e : WeightedAP) (v : Nat) : Bool :=
  v == site e 0 || v == site e 1 || v == site e 2 || v == site e 3

def changedSites (color : Nat → Nat) : List Nat :=
  (List.range 257).filter (fun v => decide (archivedColor v ≠ color v))

def CyclicABBAFree (color : Nat → Nat) : Prop :=
  ∀ a d : Nat, a < 257 → 0 < d → d < 257 →
    ¬(color (a % 257) = color ((a + 3*d) % 257) ∧
      color ((a + d) % 257) = color ((a + 2*d) % 257))

private def rowOK (e : WeightedAP) : Bool := decide
  (e.start < 257 ∧ 0 < e.step ∧ e.step < 257 ∧
   archivedColor (site e 0) = archivedColor (site e 3) ∧
   archivedColor (site e 1) = archivedColor (site e 2))

set_option maxRecDepth 100000 in
private theorem rows_valid : packing.all rowOK = true := by decide +kernel

set_option maxRecDepth 100000 in
private theorem weight_total : sumOver packing WeightedAP.weight = 16457 := by decide +kernel

private def load (v : Nat) : Nat :=
  sumOver packing (fun e => if touches e v then e.weight else 0)

set_option maxRecDepth 100000 in
set_option maxHeartbeats 0 in
private theorem load_cap : (List.range 257).all (fun v => decide (load v ≤ 257)) = true := by
  decide +kernel

private theorem hit_by_change (color : Nat → Nat) (legal : CyclicABBAFree color)
    (e : WeightedAP) (he : e ∈ packing) :
    ∃ v ∈ changedSites color, touches e v = true := by
  have cert := List.all_eq_true.mp rows_valid e he
  unfold rowOK at cert
  obtain ⟨ha, hd, hd', outer, inner⟩ := of_decide_eq_true cert
  by_cases hit : ∃ v ∈ changedSites color, touches e v = true
  · exact hit
  · exfalso
    have same (i : Nat) (hi : touches e (site e i) = true) :
        archivedColor (site e i) = color (site e i) := by
      by_cases eq : archivedColor (site e i) = color (site e i)
      · exact eq
      · exact False.elim (hit ⟨site e i,
          List.mem_filter.mpr ⟨List.mem_range.mpr (Nat.mod_lt _ (by decide)), by simp [eq]⟩,
          hi⟩)
    have h0 := same 0 (by simp [touches])
    have h1 := same 1 (by simp [touches])
    have h2 := same 2 (by simp [touches])
    have h3 := same 3 (by simp [touches])
    apply legal e.start e.step ha hd hd'
    simpa only [site, Nat.zero_mul, Nat.add_zero, Nat.one_mul] using
      And.intro (h0.symm.trans (outer.trans h3)) (h1.symm.trans (inner.trans h2))

/-- Every cyclic ABBA-free table differs from this particular archive at
at least 65 of its 257 entries, even with unrestricted natural-number colors. -/
theorem mod257_distance_at_least_65 (color : Nat → Nat) (legal : CyclicABBAFree color) :
    65 ≤ (changedSites color).length := by
  have cap (v : Nat) (hv : v ∈ changedSites color) : load v ≤ 257 :=
    of_decide_eq_true (List.all_eq_true.mp load_cap v (List.mem_filter.mp hv).1)
  have h := weighted_cover_bound packing (changedSites color) WeightedAP.weight touches 257
    (hit_by_change color legal) cap
  rw [weight_total] at h
  omega

end PathWeaverFormal.Jsp158Distance
