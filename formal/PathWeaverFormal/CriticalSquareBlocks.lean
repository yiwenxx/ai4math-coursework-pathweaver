import PathWeaverFormal.OddPowerCollisionLift

/-! A bounded-memory certificate for the 50,342 nonidentity roots. An outer
block starts at a reproducible power of ω. Within a block we advance by one
multiplication and need only five distinct nonconstant power residues per root. -/
namespace PathWeaverFormal.Jsp158.OddPower.CriticalSquare

open Lean.Grind

abbrev F := Fin 578743129
private abbrev root : F := 233991976

private def exponent : List Bool → Nat
  | [] => 1
  | b :: bits => let e := exponent bits; e+e+b.toNat

private def power (x : F) : List Bool → F
  | [] => x
  | b :: bits =>
    let z := power x bits
    let sq := z*z
    if b then sq*x else sq

private theorem power_correct (x : F) (bits : List Bool) : power x bits = x^(exponent bits) := by
  induction bits with
  | nil => exact (Semiring.pow_one _).symm
  | cons b bs ih =>
    cases b <;> simp only [power, exponent, ih, Bool.toNat_false, Bool.toNat_true,
      Bool.false_eq_true, ite_false, ite_true,
      Nat.add_zero, Semiring.pow_add, Semiring.pow_one]

private def bits : List Bool :=
  [true,true,true,false,false,true,false,true,false,false,true,false,false,false,true]

private def residue (x : F) : Nat := (power x bits).val

private theorem residue_correct (x : F) : residue x = (x^50343).val :=
  congrArg Fin.val (power_correct x bits)

private def distinct3 (x y z : Nat) : Bool := x != y && x != z && y != z

/-- In the three collision cases 01, 02, 12 we retain the three positions
023, 013, 013, respectively. The pair 12 shares a power with the pair 01. -/
private def cell (w : F) : Bool :=
  let a := residue (2*w-1)
  let b := residue (3*w-2)
  let c := residue (w+1)
  let d := residue (3*w-1)
  let e := residue (2-w)
  distinct3 1 a b && distinct3 217942094 c d && distinct3 e 1 a

private theorem use023 {a b c d : Nat} (h : distinct3 a c d = true) :
    checkTriple a b c d = true := by
  simp only [checkTriple, Bool.or_eq_true]
  exact Or.inl (Or.inr h)

private theorem use013 {a b c d : Nat} (h : distinct3 a b d = true) :
    checkTriple a b c d = true := by
  simp only [checkTriple, Bool.or_eq_true]
  exact Or.inl (Or.inl (Or.inr h))

private abbrev window (w : F) (i j : Fin 4) (t : Fin 4) :=
  ((numerator i j t w)^50343).val

private theorem one_cell {w : F} (ok : cell w=true) : collisionCheck 50343 [w]=true := by
  simp only [cell, Bool.and_eq_true_iff] at ok
  obtain ⟨⟨ha,hb⟩,hc⟩ := ok
  have n000 : numerator 0 1 0 w=1 := by change 1-0+(0-0)*(w-1)=1; grind
  have n012 : numerator 0 1 2 w=2*w-1 := by change 1-0+(2-0)*(w-1)=2*w-1; grind
  have n013 : numerator 0 1 3 w=3*w-2 := by change 1-0+(3-0)*(w-1)=3*w-2; grind
  have n020 : numerator 0 2 0 w=2 := by change 2-0+(0-0)*(w-1)=2; grind
  have n021 : numerator 0 2 1 w=w+1 := by change 2-0+(1-0)*(w-1)=w+1; grind
  have n023 : numerator 0 2 3 w=3*w-1 := by change 2-0+(3-0)*(w-1)=3*w-1; grind
  have n120 : numerator 1 2 0 w=2-w := by change 2-1+(0-1)*(w-1)=2-w; grind
  have n121 : numerator 1 2 1 w=1 := by change 2-1+(1-1)*(w-1)=1; grind
  have n123 : numerator 1 2 3 w=2*w-1 := by change 2-1+(3-1)*(w-1)=2*w-1; grind
  let g := fun i j => checkTriple (window w i j 0) (window w i j 1) (window w i j 2) (window w i j 3)
  change (g 0 1 && (g 0 2 && (g 1 2 && true)) && true) = true
  apply Bool.and_eq_true_iff.mpr
  refine ⟨Bool.and_eq_true_iff.mpr ⟨use023 ?_, Bool.and_eq_true_iff.mpr ⟨use013 ?_,
    Bool.and_eq_true_iff.mpr ⟨use013 ?_, rfl⟩⟩⟩, rfl⟩ <;>
    simp only [window,n000,n012,n013,n020,n021,n023,n120,n121,n123,← residue_correct]
  · exact ha
  · exact hb
  · exact hc

private def scan : Nat → F → Bool
  | 0, _ => true
  | n+1, w => cell w && scan n (w*root)

/-- Half-open interval of zero-based exponents, with s corresponding to ω^(s+1). -/
def Segment (lo n : Nat) : Prop :=
  ∀ s, lo ≤ s → s < lo+n → collisionCheck 50343 [root^(s+1)] = true

def block (lo n : Nat) : Bool := scan n (root^(lo+1))

theorem block_sound {lo n : Nat} (checked : block lo n=true) : Segment lo n := by
  intro s hs ht
  induction n generalizing lo with
  | zero => omega
  | succ k ih =>
    have both := Bool.and_eq_true_iff.mp checked
    by_cases eq : lo=s
    · subst s; exact one_cell both.1
    · apply ih (lo := lo+1) ?_ (by omega) (by omega)
      simpa only [block, Semiring.pow_succ root (lo+1)] using both.2

theorem join {lo a b : Nat} (left : Segment lo a) (right : Segment (lo+a) b) :
    Segment lo (a+b) := by
  intro n h hn
  by_cases hl : n < lo+a
  · exact left n h hl
  · exact right n (by omega) (by omega)

theorem complete (all : Segment 0 50342) : collisionCheck 50343 criticalRoots = true := by
  apply List.all_eq_true.mpr
  intro w mem
  obtain ⟨s, hs, rfl⟩ := List.mem_map.mp mem
  exact (Bool.and_eq_true_iff.mp (all s (Nat.zero_le s) (List.mem_range.mp hs))).1

set_option maxRecDepth 8192 in
set_option maxHeartbeats 4000000 in
/-- The first chunk is shared by the full certificate. -/
theorem first : Segment 0 128 := block_sound (by decide +kernel)

end PathWeaverFormal.Jsp158.OddPower.CriticalSquare
