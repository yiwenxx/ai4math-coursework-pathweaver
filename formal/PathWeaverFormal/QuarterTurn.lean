/- The coefficient group here is the cyclic group Z/4. -/
namespace PathWeaverFormal.QuarterTurn

/-- The value at the last site which would make the third difference zero modulo four. -/
def forbidden (x y z : Nat) : Nat := (x + y + 3*z) % 4

def Avoids (w : Nat → Nat) (n : Nat) : Prop :=
  ∀ a d : Nat, 0 < d → a + 3*d < n →
    w (a + 3*d) % 4 ≠ forbidden (w a) (w (a+d)) (w (a+2*d))

-- The least significant base-four digit is the last value of the prefix.
private def digit (p i : Nat) := (p >>> (2*i)) % 4
private def bad (p d : Nat) := forbidden (digit p (3*d-1)) (digit p (2*d-1)) (digit p (d-1))

private def blocked (p : Nat) : Nat → Nat
  | 0 => 0
  | d+1 => (1 <<< bad p (d+1)) ||| blocked p d

private def search (p j : Nat) : Nat → Bool
  | 0 => true
  | r+1 =>
    let mask := blocked p (j/3)
    [0,1,2,3].any fun x => !mask.testBit x && search (4*p+x) (j+1) r

private theorem unblocked (p x D : Nat) (h : ∀ d, 0 < d → d ≤ D → bad p d ≠ x) :
    (blocked p D).testBit x = false := by
  induction D with
  | zero => simp [blocked]
  | succ D ih =>
    have last := h (D+1) (by omega) (by omega)
    have prev := ih (fun d h1 h2 => h d h1 (by omega))
    simp [blocked, Nat.testBit_or, Nat.shiftLeft_eq, last, prev]

private def Agrees (p j : Nat) (w : Nat → Nat) : Prop :=
  ∀ i, i < j → digit p i = w (j-1-i)

private theorem append_agrees (p j x : Nat) (w : Nat → Nat)
    (hx : x < 4) (atEnd : x = w j) (agree : Agrees p j w) : Agrees (4*p+x) (j+1) w := by
  intro i hi
  cases i with
  | zero => simp [digit, ← atEnd, Nat.mod_eq_of_lt hx]
  | succ i =>
    have hr : (4*p+x) >>> 2 = p := by rw [Nat.shiftRight_eq_div_pow]; omega
    have hshift : 2*(i+1) = 2+2*i := by omega
    have ix : j+1-1-(i+1) = j-1-i := by omega
    rw [digit, hshift, Nat.shiftRight_add, hr, ix]
    exact agree i (by omega)

private theorem search_complete (w : Nat → Nat) (hw : ∀ i, w i < 4)
    (r p j : Nat) (agree : Agrees p j w) (avoids : Avoids w (j+r)) : search p j r = true := by
  induction r generalizing p j with
  | zero => rfl
  | succ r ih =>
    apply List.any_eq_true.mpr
    have choices : w j = 0 ∨ w j = 1 ∨ w j = 2 ∨ w j = 3 := by have := hw j; omega
    have mem : w j ∈ [0,1,2,3] := by simpa using choices
    refine ⟨w j, mem, Bool.and_eq_true_iff.mpr ⟨?_, ?_⟩⟩
    · suffices h : (blocked p (j/3)).testBit (w j) = false by simp [h]
      apply unblocked
      intro d hd bound
      have h := avoids (j-3*d) d hd (by omega)
      have endpt : j-3*d+3*d = j := by omega
      have mid1 : j-3*d+d = j-2*d := by omega
      have mid2 : j-3*d+2*d = j-d := by omega
      rw [endpt, mid1, mid2, Nat.mod_eq_of_lt (hw _)] at h
      have prev (v : Nat) (hv : 0 < v) (hv' : v ≤ j) : digit p (v-1) = w (j-v) := by
        have eq : j-1-(v-1) = j-v := by omega
        simpa [eq] using agree (v-1) (by omega)
      simpa [bad, prev (3*d) (by omega) (by omega), prev (2*d) (by omega) (by omega),
        prev d hd (by omega)] using Ne.symm h
    · exact ih _ _ (append_agrees p j _ w (hw _) rfl agree) (by
        simpa [Nat.add_assoc, Nat.add_comm, Nat.add_left_comm] using avoids)

private theorem children (p j r : Nat)
    (h : ∀ x ∈ [0,1,2,3], (blocked p (j/3)).testBit x = false → search (4*p+x) (j+1) r = false) :
    search p j (r+1) = false := by
  apply Bool.eq_false_iff.mpr
  intro yes
  obtain ⟨x, hx, ok⟩ := List.any_eq_true.mp yes
  obtain ⟨free, alive⟩ := Bool.and_eq_true_iff.mp ok
  have b : (blocked p (j/3)).testBit x = false := by simpa using free
  rw [h x hx b] at alive
  contradiction

section
-- Keep the nine disjoint five-digit cases separate to bound kernel memory use.
set_option maxRecDepth 100000
set_option maxHeartbeats 0
private theorem b4  : search 4 5 30 = false := by decide +kernel
private theorem b5  : search 5 5 30 = false := by decide +kernel
private theorem b6  : search 6 5 30 = false := by decide +kernel
private theorem b8  : search 8 5 30 = false := by decide +kernel
private theorem b9  : search 9 5 30 = false := by decide +kernel
private theorem b11 : search 11 5 30 = false := by decide +kernel
private theorem b12 : search 12 5 30 = false := by decide +kernel
private theorem b14 : search 14 5 30 = false := by decide +kernel
private theorem b15 : search 15 5 30 = false := by decide +kernel
end

private theorem exhausted : search 0 3 32 = false := by
  apply children
  intro x hx good
  simp at hx
  rcases hx with rfl | rfl | rfl | rfl
  · change true = false at good; contradiction
  · apply children; intro y hy ok; simp at hy
    rcases hy with rfl | rfl | rfl | rfl
    · exact b4
    · exact b5
    · exact b6
    · change true = false at ok; contradiction
  · apply children; intro y hy ok; simp at hy
    rcases hy with rfl | rfl | rfl | rfl
    · exact b8
    · exact b9
    · change true = false at ok; contradiction
    · exact b11
  · apply children; intro y hy ok; simp at hy
    rcases hy with rfl | rfl | rfl | rfl
    · exact b12
    · change true = false at ok; contradiction
    · exact b14
    · exact b15

/-- Every length-35 word over Z/4 with its first three entries zero has a zero third difference. -/
theorem normalized_length35 (w : Nat → Nat) (hw : ∀ i, w i < 4)
    (h0 : w 0 = 0) (h1 : w 1 = 0) (h2 : w 2 = 0) : ¬ Avoids w 35 := by
  intro avoid
  have same : Agrees 0 3 w := by
    intro i hi
    have cases : i = 0 ∨ i = 1 ∨ i = 2 := by omega
    rcases cases with rfl | rfl | rfl
    · exact h2.symm
    · exact h1.symm
    · exact h0.symm
  have h := search_complete w hw 32 0 3 same avoid
  rw [exhausted] at h
  contradiction

private def gauge (a b c i : Nat) : Nat :=
  let t := i%8
  (3*a + (a+3*b)*t + (2*b+3*a+3*c)*(t*(t-1)/2)) %4

private theorem gauge_law : ∀ a b c : Fin 4, ∀ x d : Fin 8,
    gauge a b c (x.val+3*d.val) = forbidden (gauge a b c x) (gauge a b c (x.val+d.val))
      (gauge a b c (x.val+2*d.val)) := by decide +kernel

private theorem gauge_zeroes : ∀ a b c : Fin 4,
    (a.val + gauge a b c 0)%4=0 ∧ (b.val + gauge a b c 1)%4=0 ∧ (c.val + gauge a b c 2)%4=0 := by
  decide +kernel

/-- Every word of length 35 has a zero third difference on a positive-step progression. -/
theorem length35
    (w : Nat → Nat) : ¬ Avoids w 35 := by
  let a : Fin 4 := ⟨w 0%4, by omega⟩
  let b : Fin 4 := ⟨w 1%4, by omega⟩
  let c : Fin 4 := ⟨w 2%4, by omega⟩
  let q := gauge a b c
  let v := fun i => (w i + q i)%4
  have zeroes := gauge_zeroes a b c
  have hz0 : v 0=0 := by dsimp [v,q]; have h := zeroes.1; change (w 0%4 + gauge a b c 0)%4=0 at h; omega
  have hz1 : v 1=0 := by dsimp [v,q]; have h := zeroes.2.1; change (w 1%4+gauge a b c 1)%4=0 at h; omega
  have hz2 : v 2=0 := by dsimp [v,q]; have h := zeroes.2.2; change (w 2%4+gauge a b c 2)%4=0 at h; omega
  intro avoids
  apply normalized_length35 v (fun i => Nat.mod_lt _ (by decide)) hz0 hz1 hz2
  intro x d hd hbound bad
  have hq : q (x+3*d) = forbidden (q x) (q (x+d)) (q (x+2*d)) := by
    have h := gauge_law a b c ⟨x%8,by omega⟩ ⟨d%8,by omega⟩
    dsimp only at h
    simpa only [q, gauge, Nat.add_mod, Nat.mul_mod, Nat.mod_mod] using h
  have h := avoids x d hd hbound
  dsimp only [v, forbidden] at bad
  dsimp only [forbidden] at hq h
  omega

/-- The table on the first `m` positions, extended periodically with colors in Z/4. -/
def table (c : Nat → Nat) (m i : Nat) := c (i%m) % 4

def QuarterShift (c : Nat → Nat) (k : Nat) : Prop :=
  ∀ i, table c (4*k) (i+k) = (table c (4*k) i + 1)%4

def CyclicFree (c : Nat → Nat) (m : Nat) : Prop :=
  ∀ a d, 0<d → d<m → table c m a = table c m (a+3*d) →
    table c m (a+d) ≠ table c m (a+2*d)

theorem quarter_turn_upper
    (c : Nat → Nat) (k : Nat)
    (quarter : QuarterShift c k) (legal : CyclicFree c (4*k)) : 4*k ≤ 44 := by
  apply Classical.byContradiction
  intro hlarge
  let w := table c (4*k)
  have hrot (i t : Nat) : w (i+t*k) = (w i+t)%4 := by
    induction t with
    | zero => simp [w,table]
    | succ t ih =>
      rw [Nat.succ_mul, ← Nat.add_assoc, show w (i+t*k+k) = (w (i+t*k)+1)%4 from quarter _, ih]
      omega
  apply (length35 w)
  intro a d hd limit zero
  let t := (w (a+d)+3*w (a+2*d))%4
  have ht : t ≤ 3 := by dsimp [t]; omega
  have mult := Nat.mul_le_mul_right k ht
  have h := legal a (d+t*k) (by omega) (by omega)
  have h0 : w a < 4 := Nat.mod_lt _ (by decide)
  have h1 : w (a+d) < 4 := Nat.mod_lt _ (by decide)
  have h2 : w (a+2*d) < 4 := Nat.mod_lt _ (by decide)
  have h3 : w (a+3*d) < 4 := Nat.mod_lt _ (by decide)
  have pos (i : Nat) : a+i*(d+t*k) = a+i*d+(i*t)*k := by
    rw [Nat.mul_add,Nat.mul_assoc,Nat.add_assoc]
  change w a = w (a+3*(d+t*k)) → w (a+(d+t*k)) ≠ w (a+2*(d+t*k)) at h
  rw [pos 3, pos 2, ← Nat.add_assoc, hrot, hrot, hrot] at h
  have hdiff : w (a+3*d)%4 = (w a + w (a+d) + 3*w (a+2*d))%4 := zero
  dsimp only [t] at h
  omega
private def word34 (i : Nat) : Nat :=
  #[0,0,0,1,0,2,2,2,1,0,0,2,0,1,3,3,2,3,0,0,0,1,0,3,1,0,1,1,3,1,2,3,1,1][i]?.getD 0

private theorem word34_check : ∀ a d : Fin 34, 0 < d.val → a.val+3*d.val < 34 →
    word34 (a.val+3*d.val)%4 ≠ forbidden (word34 a) (word34 (a.val+d.val)) (word34 (a.val+2*d.val)) := by
  decide +kernel

theorem attains34 : ∃ w, Avoids w 34 := by
  refine ⟨word34, ?_⟩
  intro a d hd bound
  exact word34_check ⟨a,by omega⟩ ⟨d,by omega⟩ hd bound

/-- A quadratic-character construction on the residue modulo eleven. -/
private def color44 (i : Nat) : Nat :=
  let r := i%11
  (3*i + (if r=0 then 1 else if [1,3,4,5,9].contains r then 0 else 3))%4

private theorem turn_check : ∀ i : Fin 44,
    table color44 44 (i.val+11) = (table color44 44 i + 1)%4 := by decide +kernel

private theorem color44_check : ∀ a d : Fin 44, 0 < d.val →
    table color44 44 a = table color44 44 (a.val+3*d.val) →
    table color44 44 (a.val+d.val) ≠ table color44 44 (a.val+2*d.val) := by decide +kernel

theorem attains44 : ∃ c, QuarterShift c 11 ∧ CyclicFree c 44 := by
  refine ⟨color44, ?_, ?_⟩
  · intro i
    change table color44 44 (i+11) = (table color44 44 i+1)%4
    have h := turn_check ⟨i%44, by omega⟩
    dsimp only at h
    simpa only [table, Nat.add_mod, Nat.mod_mod] using h
  · intro a d hd bd
    have h := color44_check ⟨a%44, by omega⟩ ⟨d,bd⟩ hd
    dsimp only at h
    simpa only [table, Nat.add_mod, Nat.mod_mod] using h

/-- Both exact extrema, including their attaining witnesses. -/
theorem exact_extrema :
    (∀ (n : Nat) (w : Nat → Nat), Avoids w n → n ≤ 34) ∧ (∃ w, Avoids w 34) ∧
    (∀ (c : Nat → Nat) (k : Nat), QuarterShift c k → CyclicFree c (4*k) → 4*k ≤ 44) ∧
    (∃ c, QuarterShift c 11 ∧ CyclicFree c 44) := by
  refine ⟨?_, attains34, quarter_turn_upper, attains44⟩
  intro n w avoid
  apply Classical.byContradiction
  intro h
  exact length35 w (fun a d hd bound => avoid a d hd (by omega))

end PathWeaverFormal.QuarterTurn
