# Lean 4 Formal Verification Integration (`lean` & `lean_proof`)

PathWeaver integrates Lean 4 (`leanprover/lean4:v4.36.0`) across four layers without third-party Python or Mathlib dependencies:

1. **Host Kernel Verifier (`src/pathweaver/research/formal_verifier.py`)**:
   - Invokes `lake env lean --json` / `lean --json` (auto-resolving `~/.elan/bin` when needed, or immutable Docker images).
   - Strips nested `/- ... -/` and `--` comments before rejecting `sorry`, `admit`, `axiom`, `opaque`, `unsafe`, `@[implemented_by]`, `@[extern]`, `native_decide`, `#eval`, `#exec`, `initialize`, `elab`, `macro_rules`, and `IO.`/`System.` escapes.
   - Enforces `#print axioms <theorem>` audit against `ALLOWED_LEAN_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}`.
   - Grants `EvidenceLevel.FORMAL_VERIFIED` **only** when zero errors, zero `sorryAx`, and only allowed kernel axioms are confirmed.

2. **Pure Lean 4 Formal Library (`formal/PathWeaverFormal/`)**:
   - `EdaDuality.lean`: Proves capacity-1 assignment weak/strong duality (`eda_weak_duality`, `eda_optimal_from_duality`) and Hall/Pigeonhole bottleneck impossibility (`no_inj_into_shorter`, `verify_eda_hall_conflict_sound`).
   - `WvcDuality.lean`: Proves weighted vertex cover integer edge-packing weak/strong duality (`wvc_weak_duality`, `wvc_optimal_from_duality`).
   - `Jsp158Coloring.lean`: Proves equivalence between the decidable 4-AP 3-color checker and `IsFourAPFree3`.
   - `FrobeniusBase.lean`: Formalizes finite-field `F_11`, quadratic extension `F_121 = F_11[w]/(w^2 - 2)`, Frobenius involution/trace/norm lemmas, and 4-AP injective map invariance.

3. **Task Certificate Export & ClaimLedger Admission (`pathweaver lean`)**:
   - `pathweaver lean info`: Inspect installed `lean`, `lake`, and `PathWeaverFormal` build status.
   - `pathweaver lean check <file.lean> [--theorem NAME]`: Run strict Lean 4 kernel check and axiom audit.
   - `pathweaver lean export-cert --task {eda,wvc,jsp158} --instance INST.json --solution SOL.json [--output OUT.lean] [--verify]`: Independently recompute constraints/duals and emit + kernel-verify a `.lean` proof certificate.
   - `pathweaver lean admit-claim --bundle BUNDLE.json --claim-id ID --file PROOF.lean [--theorem NAME] [--apply]`: Verify a `.lean` proof in the kernel before admitting `"kind": "formal_proof"` into `ClaimLedger`.

4. **Statement-Locked Lean Discovery Loop (`lean_proof` + `pathweaver discover`)**:
   - Locks the target proposition outside `_PathWeaverCandidate` (`build_locked_lean_module`) so candidates cannot weaken statements or spoof axioms.
   - Scores `(incomplete_flag, sorry_count, proof_bytes)` so partial `sorry` stubs (`HYPOTHESIS`) cannot beat or tie any complete proof `(0, 0, proof_bytes)` (`FORMAL_VERIFIED`).
   - Example zero-spend config: `configs/lean_proof.example.toml`; benchmarks: `benchmarks/lean_proof/`.
