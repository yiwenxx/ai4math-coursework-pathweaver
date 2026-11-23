import Init.Data.List.Nat.Range
import Init.Data.Nat.Lemmas
import Init.Omega

/-! Finite unit-step certificates for the two 121st-power cyclic colorings.
The public statements use natural powers modulo the indicated prime. -/

namespace PathWeaverFormal.OddPower121

/-- Count the six unordered pairs of positions whose values coincide. -/
def collisionCount (a b c d : Nat) : Nat :=
  (a == b).toNat + (a == c).toNat + (a == d).toNat +
  (b == c).toNat + (b == d).toNat + (c == d).toNat

private abbrev Good (p z a b c d : Nat) : Prop :=
  collisionCount a b c d ≤ 1 ∧
  ((z % p = 0 ∨ (z+1) % p = 0 ∨ (z+2) % p = 0 ∨ (z+3) % p = 0) →
    a ≠ b ∧ a ≠ c ∧ a ≠ d ∧ b ≠ c ∧ b ≠ d ∧ c ≠ d)

/-- Every unit-step window has at most one repeated pair. If the window
contains the input zero, all four raw powers are distinct. -/
def NormalizedWindow (p z : Nat) : Prop :=
  Good p z (z^121 % p) ((z+1)^121 % p) ((z+2)^121 % p) ((z+3)^121 % p)

private def powerStep (p x : Nat) (bit : Bool) (a : Nat) : Nat :=
  let square := a * a % p
  if bit then square * (x % p) % p else square

private theorem mulPowers (x p a b : Nat) :
    (x^a % p * (x^b % p)) % p = x^(a+b) % p := by
  rw [Nat.pow_add, Nat.mul_mod (x^a) (x^b)]

private theorem powerStep_eq (p x e : Nat) (bit : Bool) :
    powerStep p x bit (x^e % p) = x^(e+e+bit.toNat) % p := by
  cases bit with
  | false => exact mulPowers x p e e
  | true =>
    change ((x^e % p * (x^e % p) % p) * (x % p)) % p = x^(e+e+1) % p
    rw [mulPowers]
    simpa only [Nat.pow_one] using mulPowers x p (e+e) 1

private def bitsPower (p x : Nat) : List Bool → Nat
  | [] => x % p
  | bit :: rest => powerStep p x bit (bitsPower p x rest)

private def bitsExponent : List Bool → Nat
  | [] => 1
  | bit :: rest => let e := bitsExponent rest; e + e + bit.toNat

private theorem bitsPower_eq (p x : Nat) (bits : List Bool) :
    bitsPower p x bits = x^(bitsExponent bits) % p := by
  induction bits with
  | nil => simp [bitsPower, bitsExponent]
  | cons bit rest ih => simp only [bitsPower, bitsExponent, ih, powerStep_eq]

private def power (p x : Nat) : Nat :=
  bitsPower p x [true, false, false, true, true, true]

private theorem power_eq (p x : Nat) : power p x = x^121 % p :=
  bitsPower_eq p x _

/-- Reuse the last three powers when advancing to the next start. -/
private def scan (p : Nat) : Nat → Nat → Nat → Nat → Nat → Bool
  | 0, _, _, _, _ => true
  | n+1, z, a, b, c =>
    let d := power p (z+3)
    decide (Good p z a b c d) && scan p n (z+1) b c d

private abbrev block (p n s : Nat) :=
  scan p n s (power p s) (power p (s+1)) (power p (s+2))

private theorem scan_sound {p n s z : Nat} (h : block p n s = true)
    (lo : s ≤ z) (hi : z < s+n) :
    Good p z (power p z) (power p (z+1)) (power p (z+2)) (power p (z+3)) := by
  induction n generalizing s with
  | zero => omega
  | succ k ih =>
    have parts := Bool.and_eq_true_iff.mp h
    by_cases hs : s = z
    · subst s
      exact of_decide_eq_true parts.1
    · exact ih (s := s+1) parts.2 (by omega) (by omega)

private def certificate (p blocks : Nat) : Bool :=
  (List.range blocks).all fun j => block p 128 (128*j)

private theorem certificate_sound {p blocks : Nat} (h : certificate p blocks = true)
    (cover : p ≤ blocks*128) (z : Fin p) : NormalizedWindow p z := by
  have hj : z.val / 128 < blocks :=
    (Nat.div_lt_iff_lt_mul (by decide : 0 < 128)).mpr (Nat.lt_of_lt_of_le z.isLt cover)
  have part := List.all_eq_true.mp h (z.val / 128) (List.mem_range.mpr hj)
  have good := scan_sound (z := z.val) part (by omega) (by omega)
  simpa only [NormalizedWindow, power_eq] using good

set_option maxRecDepth 8192
set_option maxHeartbeats 4000000

private theorem verified13553 : certificate 13553 106 = true := by decide +kernel
private theorem verified19603 : certificate 19603 154 = true := by decide +kernel

theorem normalized13553 (z : Fin 13553) : NormalizedWindow 13553 z :=
  certificate_sound verified13553 (by decide) z

theorem normalized19603 (z : Fin 19603) : NormalizedWindow 19603 z :=
  certificate_sound verified19603 (by decide) z

end PathWeaverFormal.OddPower121
