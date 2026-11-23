import PathWeaverFormal.CriticalSquareBlocks
import Lean.Elab.Command

/-! The only generated declarations are applications of `block_sound` and
`join`. Each numerical leaf is an independent kernel reduction over at most
128 roots. The final, shorter leaf ends at the exact exponent bound. -/
namespace PathWeaverFormal.Jsp158.OddPower.CriticalSquare

open Lean Elab Command

private partial def emitBlocks (beginBlock endBlock : Nat) : CommandElabM Ident := do
  if beginBlock == 0 && endBlock == 1 then
    return mkIdent ``first
  let name := mkIdent (Name.mkSimple s!"verified_{beginBlock}_{endBlock}")
  let start := 128 * beginBlock
  let stop := min 50342 (128 * endBlock)
  let lo := Syntax.mkNumLit (toString start)
  let len := Syntax.mkNumLit (toString (stop-start))
  if endBlock == beginBlock+1 then
    elabCommand (← `(private theorem $name : Segment $lo $len :=
      block_sound (by decide +kernel)))
  else
    let middle := (beginBlock+endBlock)/2
    let left ← emitBlocks beginBlock middle
    let right ← emitBlocks middle endBlock
    elabCommand (← `(private theorem $name : Segment $lo $len := join $left $right))
  return name

elab "certify_critical_roots" : command => do
  let proof ← emitBlocks 0 394
  let named := mkIdent `certifiedRange
  elabCommand (← `(theorem $named : Segment 0 50342 := $proof))

set_option maxRecDepth 8192
set_option maxHeartbeats 4000000

certify_critical_roots

theorem verifiedCollisions : collisionCheck 50343 criticalRoots = true :=
  complete certifiedRange

/-- Explicit bound for the original finite-interval problem, without arithmetic
hypotheses. The construction is the pair of 50,343rd-power template labels. -/
theorem interval_10pow18 :
    ∃ colors : Array Nat, colors.size = 10^18 ∧ IsFourAPFree3 colors ∧
      AllColorsBelow colors 132158016 :=
  critical_interval verifiedCollisions

#print axioms interval_10pow18

end PathWeaverFormal.Jsp158.OddPower.CriticalSquare
