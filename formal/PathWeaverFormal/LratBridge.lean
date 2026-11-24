/-
PathWeaverFormal.LratBridge
Pure Lean 4.36.0 kernel-sound Reverse Unit Propagation (RUP / positive-hint LRAT)
refutation verifier for CNF unsatisfiability certificates.
-/

namespace PathWeaverFormal.LratBridge

abbrev CnfClause := List Int
abbrev CnfFormula := List CnfClause

def evalLit (σ : Nat → Bool) (lit : Int) : Bool :=
  if lit > 0 then σ (lit.toNat - 1)
  else if lit < 0 then !(σ (lit.natAbs - 1))
  else false

def evalClause (σ : Nat → Bool) (c : CnfClause) : Bool :=
  c.any (evalLit σ)

def evalFormula (σ : Nat → Bool) (F : CnfFormula) : Bool :=
  F.all (evalClause σ)

def CnfSatisfiable (F : CnfFormula) : Prop :=
  ∃ σ : Nat → Bool, evalFormula σ F = true

structure RupStep where
  id : Nat
  clause : CnfClause
  hints : List Nat
  deriving Repr, DecidableEq

theorem evalLit_zero (σ : Nat → Bool) : evalLit σ 0 = false := rfl

theorem evalLit_neg (σ : Nat → Bool) (lit : Int) (hne : lit ≠ 0) :
    evalLit σ (-lit) = !(evalLit σ lit) := by
  unfold evalLit
  by_cases hpos : lit > 0
  · have hnpos : ¬ ((-lit) > 0) := by omega
    have hnneg : (-lit) < 0 := by omega
    have habs : (-lit).natAbs = lit.toNat := by omega
    simp only [hnpos, hnneg, hpos, ↓reduceIte, habs]
  · have hneg : lit < 0 := by omega
    have hnpos : (-lit) > 0 := by omega
    have htoNat : (-lit).toNat = lit.natAbs := by omega
    simp only [hnpos, hpos, hneg, ↓reduceIte, htoNat, Bool.not_not]

theorem evalClause_nil (σ : Nat → Bool) : evalClause σ [] = false := rfl

theorem evalClause_cons (σ : Nat → Bool) (l : Int) (ls : CnfClause) :
    evalClause σ (l :: ls) = (evalLit σ l || evalClause σ ls) := rfl

theorem evalClause_false_mem {σ : Nat → Bool} {c : CnfClause}
    (h : evalClause σ c = false) :
    ∀ l ∈ c, evalLit σ l = false := by
  induction c with
  | nil =>
      intro l hl
      cases hl
  | cons x xs ih =>
      rw [evalClause_cons] at h
      cases hx : evalLit σ x <;> cases hxs : evalClause σ xs
      · intro l hl
        cases hl with
        | head => exact hx
        | tail _ hmem => exact ih hxs l hmem
      · simp [hx, hxs] at h
      · simp [hx, hxs] at h
      · simp [hx, hxs] at h

theorem evalFormula_mem {σ : Nat → Bool} {F : CnfFormula}
    (h : evalFormula σ F = true) :
    ∀ c ∈ F, evalClause σ c = true := by
  induction F with
  | nil =>
      intro c hc
      cases hc
  | cons c cs ih =>
      change (evalClause σ c && evalFormula σ cs) = true at h
      cases hc0 : evalClause σ c <;> cases hcs0 : evalFormula σ cs
      · simp [hc0] at h
      · simp [hc0] at h
      · simp [hc0, hcs0] at h
      · intro d hd
        cases hd with
        | head => exact hc0
        | tail _ hmem => exact ih hcs0 d hmem

def memInt (x : Int) : List Int → Bool
  | [] => false
  | y :: ys => (x == y) || memInt x ys

theorem memInt_sound {σ : Nat → Bool} {x : Int} {xs : List Int}
    (h : memInt x xs = true)
    (hfalse : ∀ y ∈ xs, evalLit σ y = false) :
    evalLit σ x = false := by
  induction xs with
  | nil => simp [memInt] at h
  | cons y ys ih =>
      unfold memInt at h
      simp only [Bool.or_eq_true, beq_iff_eq] at h
      cases h with
      | inl hxy =>
          subst hxy
          exact hfalse x (List.Mem.head _)
      | inr hrest =>
          exact ih hrest (fun z hz => hfalse z (List.Mem.tail _ hz))

def hasComplement : List Int → Bool
  | [] => false
  | l :: ls => (l != 0 && memInt (-l) ls) || hasComplement ls

theorem hasComplement_false {σ : Nat → Bool} {xs : List Int}
    (hc : hasComplement xs = true)
    (hfalse : ∀ y ∈ xs, evalLit σ y = false) :
    False := by
  induction xs with
  | nil => simp [hasComplement] at hc
  | cons l ls ih =>
      unfold hasComplement at hc
      simp only [Bool.or_eq_true, Bool.and_eq_true, bne_iff_ne] at hc
      cases hc with
      | inl hl =>
          have h1 : evalLit σ l = false := hfalse l (List.Mem.head _)
          have h2 : evalLit σ (-l) = false :=
            memInt_sound hl.2 (fun z hz => hfalse z (List.Mem.tail _ hz))
          rw [evalLit_neg σ l hl.1, h1] at h2
          cases h2
      | inr hrest =>
          exact ih hrest (fun z hz => hfalse z (List.Mem.tail _ hz))

inductive ReduceResult where
  | conflict
  | unit (lit : Int)
  | nonUnit
  deriving Repr, DecidableEq

def reduceClauseGo (falsified : List Int) (acc : Option Int) : CnfClause → ReduceResult
  | [] =>
      match acc with
      | none => .conflict
      | some u => .unit u
  | l :: rest =>
      if l == 0 || memInt l falsified then
        reduceClauseGo falsified acc rest
      else
        match acc with
        | none => reduceClauseGo falsified (some l) rest
        | some u =>
            if l == u then reduceClauseGo falsified (some u) rest
            else .nonUnit

def reduceClause (falsified : List Int) (c : CnfClause) : ReduceResult :=
  reduceClauseGo falsified none c

theorem reduceClauseGo_sound
    (σ : Nat → Bool)
    (falsified : List Int)
    (acc : Option Int)
    (c : CnfClause)
    (hf : ∀ x ∈ falsified, evalLit σ x = false)
    (hacc_ne : ∀ u, acc = some u → u ≠ 0)
    (hsat : (∃ u, acc = some u ∧ evalLit σ u = true) ∨ evalClause σ c = true) :
    (reduceClauseGo falsified acc c ≠ .conflict) ∧
    (∀ u, reduceClauseGo falsified acc c = .unit u → u ≠ 0 ∧ evalLit σ u = true) := by
  induction c generalizing acc with
  | nil =>
      cases acc with
      | none =>
          rcases hsat with ⟨u, hu, _⟩ | hnil
          · cases hu
          · rw [evalClause_nil] at hnil
            cases hnil
      | some u =>
          constructor
          · simp [reduceClauseGo]
          · intro w hw
            simp only [reduceClauseGo, ReduceResult.unit.injEq] at hw
            cases hw
            refine ⟨hacc_ne u rfl, ?_⟩
            rcases hsat with ⟨v, hv, hvt⟩ | hnil
            · cases hv
              exact hvt
            · rw [evalClause_nil] at hnil
              cases hnil
  | cons l rest ih =>
      unfold reduceClauseGo
      by_cases hskip : (l == 0 || memInt l falsified) = true
      · simp only [hskip, ↓reduceIte]
        have hl_false : evalLit σ l = false := by
          simp only [Bool.or_eq_true, beq_iff_eq] at hskip
          cases hskip with
          | inl h0 => subst h0; exact evalLit_zero σ
          | inr hm => exact memInt_sound hm hf
        have hsat' : (∃ u, acc = some u ∧ evalLit σ u = true) ∨ evalClause σ rest = true := by
          rcases hsat with hacc | hcl
          · exact Or.inl hacc
          · rw [evalClause_cons, hl_false] at hcl
            exact Or.inr hcl
        exact ih acc hacc_ne hsat'
      · have hskip_f : (l == 0 || memInt l falsified) = false := Bool.eq_false_iff.mpr hskip
        simp only [hskip_f]
        have hl_ne : l ≠ 0 := by
          intro h0
          subst h0
          simp at hskip_f
        cases acc with
        | none =>
            have hne' : ∀ u, some l = some u → u ≠ 0 := by
              intro u hu
              cases hu
              exact hl_ne
            have hsat' : (∃ u, some l = some u ∧ evalLit σ u = true) ∨ evalClause σ rest = true := by
              rcases hsat with ⟨u, hu, _⟩ | hcl
              · cases hu
              · rw [evalClause_cons] at hcl
                cases hl_val : evalLit σ l
                · rw [hl_val] at hcl
                  exact Or.inr hcl
                · exact Or.inl ⟨l, rfl, hl_val⟩
            exact ih (some l) hne' hsat'
        | some u =>
            by_cases hlu : (l == u) = true
            · simp only [hlu, ↓reduceIte]
              have heq : l = u := beq_iff_eq.mp hlu
              have hsat' : (∃ v, some u = some v ∧ evalLit σ v = true) ∨ evalClause σ rest = true := by
                rcases hsat with ⟨v, hv, hvt⟩ | hcl
                · exact Or.inl ⟨v, hv, hvt⟩
                · rw [evalClause_cons] at hcl
                  cases hl_val : evalLit σ l
                  · rw [hl_val] at hcl
                    exact Or.inr hcl
                  · rw [heq] at hl_val
                    exact Or.inl ⟨u, rfl, hl_val⟩
              exact ih (some u) hacc_ne hsat'
            · have hlu_f : (l == u) = false := Bool.eq_false_iff.mpr hlu
              simp only [hlu_f]
              constructor
              · intro hcon
                cases hcon
              · intro w hw
                cases hw

theorem reduceClause_sound
    (σ : Nat → Bool)
    (falsified : List Int)
    (c : CnfClause)
    (hf : ∀ x ∈ falsified, evalLit σ x = false)
    (hc : evalClause σ c = true) :
    (reduceClause falsified c ≠ .conflict) ∧
    (∀ u, reduceClause falsified c = .unit u → u ≠ 0 ∧ evalLit σ u = true) :=
  reduceClauseGo_sound σ falsified none c hf (fun _ h => by cases h) (Or.inr hc)

def lookupClause (cid : Nat) : List (Nat × CnfClause) → Option CnfClause
  | [] => none
  | (k, c) :: rest => if k == cid then some c else lookupClause cid rest

theorem lookupClause_sound
    (σ : Nat → Bool)
    (cid : Nat)
    (active : List (Nat × CnfClause))
    (c : CnfClause)
    (hact : ∀ p ∈ active, evalClause σ p.2 = true)
    (hlookup : lookupClause cid active = some c) :
    evalClause σ c = true := by
  induction active with
  | nil =>
      simp [lookupClause] at hlookup
  | cons p rest ih =>
      rcases p with ⟨k, c0⟩
      unfold lookupClause at hlookup
      by_cases hk : (k == cid) = true
      · simp only [hk, ↓reduceIte, Option.some.injEq] at hlookup
        subst hlookup
        exact hact (k, c0) (List.Mem.head _)
      · have hk_f : (k == cid) = false := Bool.eq_false_iff.mpr hk
        simp only [hk_f] at hlookup
        exact ih (fun q hq => hact q (List.Mem.tail _ hq)) hlookup

def proveRupLoop (active : List (Nat × CnfClause)) (falsified : List Int) : List Nat → Bool
  | [] => false
  | hid :: rest =>
      match lookupClause hid active with
      | none => false
      | some c =>
          match reduceClause falsified c with
          | .conflict => true
          | .unit u => proveRupLoop active ((-u) :: falsified) rest
          | .nonUnit => false

theorem proveRupLoop_sound
    (σ : Nat → Bool)
    (active : List (Nat × CnfClause))
    (falsified : List Int)
    (hints : List Nat)
    (hact : ∀ p ∈ active, evalClause σ p.2 = true)
    (hf : ∀ x ∈ falsified, evalLit σ x = false)
    (hloop : proveRupLoop active falsified hints = true) :
    False := by
  induction hints generalizing falsified with
  | nil =>
      simp [proveRupLoop] at hloop
  | cons hid rest ih =>
      unfold proveRupLoop at hloop
      cases hlook : lookupClause hid active with
      | none =>
          simp [hlook] at hloop
      | some c =>
          simp only [hlook] at hloop
          have hc : evalClause σ c = true := lookupClause_sound σ hid active c hact hlook
          have hred := reduceClause_sound σ falsified c hf hc
          cases hr : reduceClause falsified c with
          | conflict =>
              exact hred.1 hr
          | unit u =>
              simp only [hr] at hloop
              have hu := hred.2 u hr
              have hf' : ∀ x ∈ ((-u) :: falsified), evalLit σ x = false := by
                intro x hx
                cases hx with
                | head =>
                    rw [evalLit_neg σ u hu.1, hu.2]
                    rfl
                | tail _ hmem =>
                    exact hf x hmem
              exact ih ((-u) :: falsified) hf' hloop
          | nonUnit =>
              simp [hr] at hloop

def proveRup (active : List (Nat × CnfClause)) (clause : CnfClause) (hints : List Nat) : Bool :=
  hasComplement clause || proveRupLoop active clause hints

theorem proveRup_sound
    (σ : Nat → Bool)
    (active : List (Nat × CnfClause))
    (clause : CnfClause)
    (hints : List Nat)
    (hact : ∀ p ∈ active, evalClause σ p.2 = true)
    (hrup : proveRup active clause hints = true) :
    evalClause σ clause = true := by
  cases hcl : evalClause σ clause
  · exfalso
    have hfalse : ∀ l ∈ clause, evalLit σ l = false := evalClause_false_mem hcl
    unfold proveRup at hrup
    simp only [Bool.or_eq_true] at hrup
    cases hrup with
    | inl hcomp => exact hasComplement_false hcomp hfalse
    | inr hloop => exact proveRupLoop_sound σ active clause hints hact hfalse hloop
  · rfl

def initActive (nextId : Nat) : CnfFormula → List (Nat × CnfClause)
  | [] => []
  | c :: cs => (nextId, c) :: initActive (nextId + 1) cs

theorem initActive_sound (σ : Nat → Bool) (F : CnfFormula) (nextId : Nat)
    (hF : evalFormula σ F = true) :
    ∀ p ∈ initActive nextId F, evalClause σ p.2 = true := by
  induction F generalizing nextId with
  | nil =>
      intro p hp
      cases hp
  | cons c cs ih =>
      intro p hp
      change (evalClause σ c && evalFormula σ cs) = true at hF
      simp only [Bool.and_eq_true] at hF
      unfold initActive at hp
      cases hp with
      | head => exact hF.1
      | tail _ hmem => exact ih (nextId + 1) hF.2 p hmem

def checkRupSteps (active : List (Nat × CnfClause)) (lastId : Nat) (derivedEmpty : Bool) :
    List RupStep → Bool
  | [] => derivedEmpty
  | step :: rest =>
      if step.id > lastId && proveRup active step.clause step.hints then
        checkRupSteps
          ((step.id, step.clause) :: active)
          step.id
          (derivedEmpty || step.clause.isEmpty)
          rest
      else
        false

theorem checkRupSteps_sound
    (σ : Nat → Bool)
    (active : List (Nat × CnfClause))
    (lastId : Nat)
    (derivedEmpty : Bool)
    (steps : List RupStep)
    (hact : ∀ p ∈ active, evalClause σ p.2 = true)
    (hemp : derivedEmpty = true → False)
    (hcheck : checkRupSteps active lastId derivedEmpty steps = true) :
    False := by
  induction steps generalizing active lastId derivedEmpty with
  | nil =>
      exact hemp hcheck
  | cons step rest ih =>
      unfold checkRupSteps at hcheck
      by_cases hok : (step.id > lastId && proveRup active step.clause step.hints) = true
      · simp only [hok, ↓reduceIte] at hcheck
        simp only [Bool.and_eq_true] at hok
        have hclause : evalClause σ step.clause = true :=
          proveRup_sound σ active step.clause step.hints hact hok.2
        have hact' : ∀ p ∈ ((step.id, step.clause) :: active), evalClause σ p.2 = true := by
          intro p hp
          cases hp with
          | head => exact hclause
          | tail _ hmem => exact hact p hmem
        have hemp' : (derivedEmpty || step.clause.isEmpty) = true → False := by
          intro hd
          simp only [Bool.or_eq_true] at hd
          cases hd with
          | inl hd0 => exact hemp hd0
          | inr he =>
              cases hcl : step.clause with
              | nil =>
                  rw [hcl, evalClause_nil] at hclause
                  cases hclause
              | cons _ _ =>
                  simp [hcl] at he
        exact ih ((step.id, step.clause) :: active) step.id (derivedEmpty || step.clause.isEmpty)
          hact' hemp' hcheck
      · have hok_f : (step.id > lastId && proveRup active step.clause step.hints) = false :=
          Bool.eq_false_iff.mpr hok
        simp only [hok_f] at hcheck
        cases hcheck

def checkRupRefutation (F : CnfFormula) (steps : List RupStep) : Bool :=
  checkRupSteps (initActive 1 F) F.length false steps

theorem rup_chain_unsat (F : CnfFormula) (steps : List RupStep)
    (h : checkRupRefutation F steps = true) :
    ¬ CnfSatisfiable F := by
  intro ⟨σ, hσ⟩
  exact checkRupSteps_sound σ (initActive 1 F) F.length false steps
    (initActive_sound σ F 1 hσ) (fun hd => by cases hd) h

#print axioms rup_chain_unsat

end PathWeaverFormal.LratBridge
