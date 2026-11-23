import PathWeaverFormal.TwoDigitCyclicLift
import Init.GrindInstances.Ring.Fin
import Init.Data.List.FinRange
import Init.Data.List.Perm
import Init.Data.Nat.Coprime
import Lean.Elab.Tactic.Grind

namespace PathWeaverFormal.Jsp158.OddPower
open Lean.Grind

private abbrev idx (p : Nat) [NeZero p] (i : Fin 4) : Fin p := Fin.ofNat p i.val

private abbrev Three (f : Fin 4 → Nat) :=
  AtLeastThreeColors (f 0) (f 1) (f 2) (f 3)

private theorem transport {f g : Fin 4 → Nat}
    (refines : ∀ i j, f i = f j → g i = g j) (h : Three g) : Three f := by
  have tr {i j : Fin 4} : g i ≠ g j → f i ≠ f j := fun hn eq => hn (refines i j eq)
  rcases h with ⟨a,b,c⟩ | ⟨a,b,c⟩ | ⟨a,b,c⟩ | ⟨a,b,c⟩
  · exact Or.inl ⟨tr a,tr b,tr c⟩
  · exact Or.inr (Or.inl ⟨tr a,tr b,tr c⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨tr a,tr b,tr c⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨tr a,tr b,tr c⟩))

private def firstPairs : List (Fin 4 × Fin 4) := [(0,1), (0,2), (1,2)]

/-- If positions i,j collide with multiplier w, these four numerators are a
    common scaling of the normalized window. There is no division by w−1. -/
def numerator {p : Nat} [NeZero p] (i j t : Fin 4) (w : Fin p) : Fin p :=
  idx p j - idx p i + (idx p t - idx p i)*(w-1)

/-- Only collisions within the first three positions need to generate cases.
    Each generated case checks all four colors. Runtime depends on the root
    list, not on the number of residues modulo p. -/
def collisionCheck {p : Nat} [NeZero p] (h : Nat) (roots : List (Fin p)) : Bool :=
  roots.all fun w => firstPairs.all fun (i,j) =>
    let v := fun t => ((numerator i j t w)^h).val
    checkTriple (v 0) (v 1) (v 2) (v 3)

/-- At a zero position the other three raw powers must be distinct, since
    the zero color may be merged with any one of them. -/
def zeroCheck (p h : Nat) [NeZero p] : Bool :=
  (List.finRange 4).all fun i => (List.finRange 4).all fun j => (List.finRange 4).all fun k =>
    decide (i = j ∨ i = k ∨ j = k ∨ (idx p j - idx p i)^h ≠ (idx p k - idx p i)^h)

private theorem scale_cancel {p h : Nat} [NeZero p] (d v x y : Fin p)
    (unit : d*v=1) (eq : (d*x)^h = (d*y)^h) : x^h = y^h := by
  rw [CommSemiring.mul_pow, CommSemiring.mul_pow] at eq
  have hpow : d^h*v^h=1 := by rw [← CommSemiring.mul_pow, unit, Semiring.one_pow]
  grind

private theorem other_three (f : Fin 4 → Nat) (i : Fin 4)
    (h : ∀ j k, i ≠ j → i ≠ k → j ≠ k → f j ≠ f k) : Three f := by
  have cases : i = 0 ∨ i = 1 ∨ i = 2 ∨ i = 3 := by omega
  rcases cases with rfl | rfl | rfl | rfl
  · exact Or.inr (Or.inr (Or.inr ⟨h 1 2 (by decide) (by decide) (by decide),
      h 1 3 (by decide) (by decide) (by decide), h 2 3 (by decide) (by decide) (by decide)⟩))
  · exact Or.inr (Or.inr (Or.inl ⟨h 0 2 (by decide) (by decide) (by decide),
      h 0 3 (by decide) (by decide) (by decide), h 2 3 (by decide) (by decide) (by decide)⟩))
  · exact Or.inr (Or.inl ⟨h 0 1 (by decide) (by decide) (by decide),
      h 0 3 (by decide) (by decide) (by decide), h 1 3 (by decide) (by decide) (by decide)⟩)
  · exact Or.inl ⟨h 0 1 (by decide) (by decide) (by decide),
      h 0 2 (by decide) (by decide) (by decide), h 1 2 (by decide) (by decide) (by decide)⟩

/-- A finite list of nonidentity h-th roots and two executable checks suffice
    for arbitrary steps. The group hypotheses state invertibility and coverage
    of the root list separately from the collision calculation. -/
theorem every_step {p : Nat} [NeZero p] (hp : 3 < p) (h : Nat) (roots : List (Fin p))
    (units : ∀ x : Fin p, x ≠ 0 → ∃ v, x*v=1)
    (covers : ∀ w : Fin p, w^h=1 → w ≠ 1 → w ∈ roots)
    (collisions : collisionCheck h roots = true) (zeros : zeroCheck p h = true)
    (color : Fin p → Nat)
    (reflects : ∀ x y, x ≠ 0 → y ≠ 0 → color x = color y → x^h=y^h)
    (a d : Fin p) (hd : d ≠ 0) :
    AtLeastThreeColors (color a) (color (a+d)) (color (a+2*d)) (color (a+3*d)) := by
  obtain ⟨v, hv⟩ := units d hd
  let x := fun t : Fin 4 => a + idx p t * d
  have inject {i j : Fin 4} (eq : x i = x j) : i=j := by
    change a + idx p i*d = a + idx p j*d at eq
    have e : idx p i = idx p j := by grind
    have ei : i.val < p := by omega
    have ej : j.val < p := by omega
    apply Fin.ext
    simpa [idx, Fin.ofNat, Nat.mod_eq_of_lt ei, Nat.mod_eq_of_lt ej] using congrArg Fin.val e
  have goal : Three (fun i => color (x i)) := by
    by_cases zero : ∃ i, x i = 0
    · obtain ⟨i,hi⟩ := zero
      apply other_three _ i
      intro j k hij hik hjk eq
      have nonzero {t} (hne : i ≠ t) : x t ≠ 0 := fun hz => hne (inject (hi.trans hz.symm))
      have e := reflects _ _ (nonzero hij) (nonzero hik) eq
      have valAt (t : Fin 4) : x t = d*(idx p t - idx p i) := by
        change a + idx p i*d = 0 at hi
        dsimp [x]
        grind
      rw [valAt j, valAt k] at e
      have checked := List.all_eq_true.mp (List.all_eq_true.mp (List.all_eq_true.mp zeros i (by simp))
        j (by simp)) k (by simp)
      have neq := _root_.of_decide_eq_true checked
      exact (neq.resolve_left hij |>.resolve_left hik |>.resolve_left hjk) (scale_cancel d v _ _ hv e)
    · have nz (i : Fin 4) : x i ≠ 0 := fun e => zero ⟨i,e⟩
      have witness (i j : Fin 4) (pair : (i,j) ∈ firstPairs) (hij : i ≠ j)
          (eq : color (x i) = color (x j)) : Three (fun t => color (x t)) := by
        obtain ⟨u,hu⟩ := units (x i) (nz i)
        let w := x j * u
        have he := reflects _ _ (nz i) (nz j) eq
        have hw : w^h = 1 := by
          dsimp [w]
          rw [CommSemiring.mul_pow, ← he, ← CommSemiring.mul_pow, hu, Semiring.one_pow]
        have hx : w * x i = x j := by dsimp [w]; grind
        have notOne : w ≠ 1 := by
          intro ew
          rw [ew, Semiring.one_mul] at hx
          exact hij (inject hx)
        have checked := List.all_eq_true.mp (List.all_eq_true.mp collisions w (covers w hw notOne)) (i,j) pair
        let g := fun t => ((numerator i j t w)^h).val
        have good : Three g := checkTriple_sound checked
        apply transport (g := g) _ good
        intro t s same
        have orig := reflects _ _ (nz t) (nz s) same
        have scale (t : Fin 4) : d * numerator i j t w = (w-1)*x t := by
          change w*(a+idx p i*d) = a+idx p j*d at hx
          dsimp [numerator,x]
          grind
        apply congrArg Fin.val
        apply scale_cancel d v _ _ hv
        rw [scale, scale, CommSemiring.mul_pow, CommSemiring.mul_pow, orig]
      by_cases h01 : color (x 0) = color (x 1)
      · exact witness 0 1 (by decide) (by decide) h01
      by_cases h02 : color (x 0) = color (x 2)
      · exact witness 0 2 (by decide) (by decide) h02
      by_cases h12 : color (x 1) = color (x 2)
      · exact witness 1 2 (by decide) (by decide) h12
      exact Or.inl ⟨h01,h02,h12⟩
  change AtLeastThreeColors (color (a+0*d)) (color (a+1*d)) (color (a+2*d)) (color (a+3*d)) at goal
  simpa only [Semiring.zero_mul, Semiring.one_mul, AddCommMonoid.add_zero] using goal

open Fin.NatCast

private theorem cast_mod {p : Nat} [NeZero p] (n : Nat) :
    ((n % p : Nat) : Fin p) = (n : Fin p) :=
  Fin.ext (Nat.mod_mod n p)

/-- Use the canonical representatives from the integer two-digit lift. -/
theorem cyclic_of_every_step {p : Nat} [NeZero p] (color : Fin p → Nat)
    (allSteps : ∀ a d : Fin p, d ≠ 0 →
      AtLeastThreeColors (color a) (color (a+d)) (color (a+2*d)) (color (a+3*d))) :
    CyclicThreeColors p (fun n => color (n : Fin p)) := by
  intro a d hd
  have nz : (d : Fin p) ≠ 0 := fun eq => hd (congrArg Fin.val eq)
  simpa only [cast_mod, Semiring.natCast_add, Semiring.natCast_mul,
    show ((2 : Nat) : Fin p) = 2 from rfl, show ((3 : Nat) : Fin p) = 3 from rfl]
    using allSteps (a : Fin p) (d : Fin p) nz

private def indexedColor {p : Nat} [NeZero p] (h : Nat) (palette : List (Fin p))
    (x : Fin p) : Nat := if x = 0 then 0 else palette.idxOf (x^h)

private theorem indexed_reflects {p h : Nat} [NeZero p] (palette : List (Fin p))
    (image : ∀ x : Fin p, x ≠ 0 → x^h ∈ palette)
    (x y : Fin p) (hx : x ≠ 0) (hy : y ≠ 0)
    (eq : indexedColor h palette x = indexedColor h palette y) : x^h = y^h := by
  simp only [indexedColor, ite_eq_right hx, ite_eq_right hy] at eq
  have get (z : Fin p) (hz : z ≠ 0) : palette[palette.idxOf (z^h)]? = some (z^h) :=
    List.getElem?_eq_some_iff.mpr ⟨List.idxOf_lt_length_of_mem (image z hz), List.getElem_idxOf _⟩
  exact Option.some.inj ((get x hx).symm.trans ((congrArg (fun i => palette[i]?) eq).trans (get y hy)))

/-- Tables named explicitly by the published generator and subgroup order. -/
def criticalRoots : List (Fin 578743129) :=
  (List.range 50342).map fun s => (233991976 : Fin 578743129)^(s+1)

def criticalPalette : List (Fin 578743129) :=
  (List.range 11496).map fun s => (7 : Fin 578743129)^(50343*s)

private theorem pow_times {p : Nat} [NeZero p] (x : Fin p) (a b : Nat) :
    x^(a*b) = (x^a)^b := by
  induction b with
  | zero => simp [Semiring.pow_zero]
  | succ b ih => rw [Nat.mul_succ, Semiring.pow_add, ih, Semiring.pow_succ]

private theorem reduce_period {p n : Nat} [NeZero p] (x : Fin p) (cycle : x^n=1) (m : Nat) :
    x^(m%n) = x^m := by
  calc
    x^(m%n) = x^(m%n) * (x^n)^(m/n) := by rw [cycle, Semiring.one_pow, Semiring.mul_one]
    _ = x^m := by rw [← pow_times, ← Semiring.pow_add, Nat.mod_add_div]

private def shortOrder {p : Nat} [NeZero p] (x : Fin p) (l : Nat) : Bool :=
  (List.range l).all fun i => decide (i=0 ∨ x^i ≠ 1)

private theorem component_dvd {p k l n : Nat} [NeZero p] (g : Fin p)
    (hl : 0 < l) (cycle : (g^k)^l=1) (short : shortOrder (g^k) l = true)
    (one : g^n=1) : l ∣ n := by
  have scaled : (g^k)^n = 1 := by
    rw [← pow_times, Nat.mul_comm, pow_times, one, Semiring.one_pow]
  have remone := (reduce_period _ cycle n).trans scaled
  have eq := _root_.of_decide_eq_true
    (List.all_eq_true.mp short (n%l) (List.mem_range.mpr (Nat.mod_lt _ hl)))
  exact Nat.dvd_of_mod_eq_zero (eq.resolve_right (fun h => h remone))

private abbrev base : Fin 578743129 := 7

set_option maxRecDepth 12000 in
set_option maxHeartbeats 3000000 in
/-- Full order of 7 modulo the actual large modulus. The only enumerations
    are in the five prime-power factors, the largest of which is 479. -/
theorem critical_order (n : Nat) (one : base^n=1) : 578743128 ∣ n := by
  have d8 := component_dvd (k := 72342891) (l := 8) base (by decide) (by decide +kernel) (by decide +kernel) one
  have d9 := component_dvd (k := 64304792) (l := 9) base (by decide) (by decide +kernel) (by decide +kernel) one
  have d97 := component_dvd (k := 578743128/97) (l := 97) base (by decide) (by decide +kernel) (by decide +kernel) one
  have d173 := component_dvd (k := 578743128/173) (l := 173) base (by decide) (by decide +kernel) (by decide +kernel) one
  have d479 := component_dvd (k := 578743128/479) (l := 479) base (by decide) (by decide +kernel) (by decide +kernel) one
  have h72 := Nat.Coprime.mul_dvd_of_dvd_of_dvd (m := 8) (n := 9) (by decide) d8 d9
  have h6984 := Nat.Coprime.mul_dvd_of_dvd_of_dvd (m := 72) (n := 97) (by decide) h72 d97
  have h1208232 := Nat.Coprime.mul_dvd_of_dvd_of_dvd (m := 6984) (n := 173) (by decide) h6984 d173
  exact Nat.Coprime.mul_dvd_of_dvd_of_dvd (m := 6984*173) (n := 479) (by decide) h1208232 d479

private theorem powers_cover {p m : Nat} [NeZero p] (g : Fin p) (count : m+1=p)
    (nontrivial : (0 : Fin p) ≠ 1) (cycle : g^m=1)
    (order : ∀ n, g^n=1 → m ∣ n) (x : Fin p) (nx : x ≠ 0) :
    ∃ n < m, g^n=x := by
  let powers := (List.range m).map (fun n => g^n)
  have size : powers.length=m := by simp [powers]
  have unit (i : Nat) (hi : i ≤ m) : g^i*g^(m-i)=1 := by
    rw [← Semiring.pow_add, show i+(m-i)=m by omega, cycle]
  have nonzero : (0 : Fin p) ∉ powers := by
    intro h
    obtain ⟨i, hi, hz⟩ := List.mem_map.mp h
    have iv := unit i (Nat.le_of_lt (List.mem_range.mp hi))
    rw [hz, Semiring.zero_mul] at iv
    exact nontrivial iv
  have distinct (i j : Nat) (hi : i<j) (hj : j<m) : g^i ≠ g^j := by
    intro same
    have hv := unit i (by omega)
    have shift : g^i*g^(j-i)=g^i := by rw [← Semiring.pow_add, show i+(j-i)=j by omega, ← same]
    have hu : g^(j-i)=1 := by grind
    have le := Nat.le_of_dvd (show 0 < j-i by omega) (order _ hu)
    omega
  have nodup : powers.Nodup := by
    apply List.pairwise_iff_getElem.mpr
    intro i j _ hj hij
    simpa [powers] using distinct i j hij (by omega)
  by_cases member : x ∈ powers
  · obtain ⟨n, hn, eq⟩ := List.mem_map.mp member
    exact ⟨n, List.mem_range.mp hn, eq⟩
  · have tooMany : (x :: 0 :: powers).Nodup := by simp [nx, member, nonzero, nodup]
    have sub : (x :: 0 :: powers) ⊆ List.finRange p := by intro _ _; simp
    have bound := tooMany.length_le_of_subset sub
    simp only [List.length_cons, size, List.length_finRange] at bound
    omega

private theorem critical_powers (x : Fin 578743129) (nx : x ≠ 0) :
    ∃ n < 578743128, base^n=x :=
  powers_cover base (by decide) (by decide) (by decide +kernel) critical_order x nx

private theorem critical_units (x : Fin 578743129) (nx : x ≠ 0) : ∃ v, x*v=1 := by
  obtain ⟨n, hn, rfl⟩ := critical_powers x nx
  exact ⟨base^(578743128-n), by rw [← Semiring.pow_add, show n+(578743128-n)=578743128 by omega]; decide +kernel⟩

private theorem critical_covers (w : Fin 578743129) (power : w^50343=1) (ne : w≠1) :
    w ∈ criticalRoots := by
  have nz : w≠0 := by intro hw; subst w; exact (by decide +kernel : (0 : Fin 578743129)^50343 ≠ 1) power
  obtain ⟨n, hn, rfl⟩ := critical_powers w nz
  have multiple := critical_order (n*50343) (by rwa [pow_times])
  obtain ⟨j,hj⟩ := Nat.dvd_of_mul_dvd_mul_right (m := 11496) (n := n) (by decide : 0 < 50343) multiple
  have positive : j≠0 := by intro z; subst j; simp [hj, Semiring.pow_zero] at ne
  refine List.mem_map.mpr ⟨j-1, List.mem_range.mpr (by omega), ?_⟩
  change (233991976 : Fin 578743129)^(j-1+1)=base^n
  rw [show j-1+1=j by omega, ← show base^11496 = 233991976 by decide +kernel, ← pow_times, ← hj]

private theorem critical_image (x : Fin 578743129) (nx : x ≠ 0) : x^50343 ∈ criticalPalette := by
  obtain ⟨n, _, rfl⟩ := critical_powers x nx
  refine List.mem_map.mpr ⟨n%11496, List.mem_range.mpr (Nat.mod_lt _ (by decide)), ?_⟩
  change base^(50343*(n%11496))=(base^n)^50343
  rw [pow_times, reduce_period (base^50343) (show (base^50343)^11496=1 by decide +kernel),
    ← pow_times, Nat.mul_comm, pow_times]

/-- The four windows which contain zero are certified directly by the kernel. -/
theorem critical_zero : zeroCheck 578743129 50343 = true := by decide +kernel

/-- The remaining numerical hypothesis checks three windows for each of
    exactly 50,342 nonidentity roots. All group and palette facts are proved. -/
theorem critical_interval
    (collisions : collisionCheck 50343 criticalRoots = true) :
    ∃ colors : Array Nat, colors.size = 10^18 ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 := by
  let color := indexedColor 50343 criticalPalette
  apply criticalSquare_10pow18 (fun n => color (n : Fin 578743129))
  · intro n _
    change (if (n : Fin 578743129) = 0 then 0 else criticalPalette.idxOf ((n : Fin 578743129)^50343)) < _
    split
    · decide
    · next h =>
        have size : criticalPalette.length = 11496 := by simp [criticalPalette]
        exact size ▸ List.idxOf_lt_length_of_mem (critical_image (n : Fin 578743129) h)
  · exact cyclic_of_every_step color (every_step (by decide) 50343 criticalRoots critical_units critical_covers
      collisions critical_zero color (indexed_reflects criticalPalette critical_image))

end PathWeaverFormal.Jsp158.OddPower
