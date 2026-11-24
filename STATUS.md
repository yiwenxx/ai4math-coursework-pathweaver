# Current status

Updated: 2026-11-24 · Public development version: `0.2.0.dev1`

## Next-Gen AI4Math Harness Upgrades & Audit Fixes (2026-11-24)

- **Universal mathematical certificates & Lean RUP bridge (`core/certificates.py`, `formal/PathWeaverFormal/LratBridge.lean`)**: Added pure-Lean 4 `LratBridge.lean` (`rup_chain_unsat`, zero `sorry`) alongside host verifiers for `LRAT` SAT refutations (`verify_lrat_unsat`, `export_rup_lean_certificate`), exact-rational `VIPR` LP/MILP duals (`verify_vipr_milp_bound`), and sparse multivariate `Nullstellensatz` obstructions (`verify_nullstellensatz_obstruction`).
- **Constructive PatternBoost, `ddmin`, metamorphic & surrogate checks (`core/constructive.py`, `core/ddmin.py`, `evaluation/metamorphic.py`, `evaluation/surrogate.py`, `tasks/jsp158_coloring/patternboost.py`)**: Added Zeller delta-debugging `ddmin_reduce`, two-phase `run_patternboost` (`pathweaver jsp158 patternboost`), isomorphic `permute_instance` + empirical scaling estimation, and ridge-regularized `SurrogateCalibrator`.
- **Warm Lean 4 LSP pool, Apollo repair, premise/OEIS retrieval & Blueprint (`research/lean_server.py`, `research/lean_repair.py`, `research/premise_retrieval.py`, `research/blueprint.py`, `research/claims.py`)**: Added persistent `LeanServerPool`, subgoal-rewarding `lean_proof` scoring and `repair_lean_proof`, `PremiseIndex` + sequence recognizer (`pathweaver lean premises`, `pathweaver lean repair`), theorem-bound multi-theorem `ClaimLedger` verification, `BlueprintCompiler` (`pathweaver claims blueprint`), AST structural fingerprinting, MAP-Elites clone penalties, and noise-immune cached SQLite retrieval.

## Four-layer epistemic memory & witness reducers (2026-11-24)

- Upgraded the research-memory stack with zero-cost L0 parent-child behavioral deltas (`memory/delta.py`, `# pathweaver-hypothesis:` / `# pathweaver-lesson:` attribution parsing), 3-slot structural + UCB-attributed retrieval (`memory/retrieval.py`), compact Prefix-Cache-safe prompt assembly (`context.py`, `context_adapter.py`), and persistent `StructuralStagnationMonitor` regime obstruction tracking (`strategy_escape.py`).
- Added dual-speed event-triggered `MemoryConsolidator` (`research/consolidator.py`, zero-cost sterile retirement / hypothesis adjudication / stepping-stone crystallization + anti-hallucination LLM gating), `ExperimentSelector` (`research/experiment_selector.py`) with domain-isolated `reduce_instance` witness reducers across EDA (`eda_assignment`), WVC (`weighted_vertex_cover`), and JSP-000158 (`jsp158_coloring`), plus `ClaimLedger.extract_search_constraints()` and `build_empirical_conjecture_bundle()`.

## JSP-000158 Lean 4 finite bounds & obstruction update (2026-11-22 — 2026-11-23)

- Added 17 zero-`sorry` Lean 4 modules to `PathWeaverFormal` (21 public modules total), unconditionally certifying `h(10^18) <= 132,158,016` (extended to `3p^2 + p + 1 = 1,004,830,828,672,875,053`), `h(137) <= 9`, `h(98) <= 8`, exact forced-rainbow threshold `19`, odd-power collision lifts (`OddPower121`, `OddPowerCollisionLift`), and core identities of the nonseparable/nonpolynomial obstruction manuscript (`NONSEPARABLE-AND-NONPOLYNOMIAL-OBSTRUCTIONS.zh-CN.md`).
- Added `pathweaver jsp158 verify-template` / `verify-digit-lift`, pure-stdlib finite colorer `scripts/color_jsp158_cyclic_product.py`, cyclic SAT sweep `scripts/sweep_cyclic_abba.py`, and machine-checked witness datasets (`jsp158_quarter_breakthrough_sweep.json`, `jsp158_nine_color_cycle/template.json`, `jsp158_nine_color_interval/witness.json`, `jsp158_forced_rainbow/certificate.py`).

## Core contraction (2026-11-21)

To maximize research agility and eliminate unnecessary ceremony, non-essential offline wrappers (Markdown/Git vault, illustrative demo, offline rule-only reflection/frontier stubs, Mermaid renderer, legacy single-edge Bookshelf adapter, and unimplemented scheduling stubs) were removed. The repository now focuses exclusively on four verified, high-leverage pillars:

| Capability | State |
|---|---|
| Installable lightweight package (`0.2.0.dev1`) & CLI (`eda`, `wvc`, `jsp158`, `claims`, `lean`) | Available |
| Lean 4 formal verification (`PathWeaverFormal`, `pathweaver lean`, `lean_proof` TaskPack & EDA/WVC/JSP158 Lean certificate export) | Verified live with `leanprover/lean4:v4.36.0` (zero Mathlib, zero `sorry`, `#print axioms` audited) |
| EDA path-coupled assignment + solver-independent Hungarian primal–dual certificate (`--require-certificate`) | Verified live on fixtures, Open3DBench AES (`(744915, 32038820)`) and Ibex (`(1663875, 47840820)`) → `finite_optimal`; tampered duals rejected |
| Weighted Minimum Vertex Cover transfer TaskPack (`pathweaver wvc`) | Implemented & verified (independent dual lower bound, baseline, tiny exact solver, discovery adapter) |
| JSP-000158 4-AP verifier, legal seed & small finite-field counterexample probe (`ff_probe.py`) | Implemented & verified locally (reproduces Nov19-005 trace-denominator counterexample over `F_25`) |
| JSP-000158 `q=121` mixed-curve certificate (`scripts/certify_q121.py`) | Generated & zero-trust verified across 4,880 depressed irreducibles, 40,656 groups and 4,919,376 equations (`SHA256: 6e6ff98dcd4595dad3634a495176e5ba60fa321ef515c4a865413ef6ead3d8fd`) |
| Lossless integer-tuple AdaEvolve ordering (`exact_ordering.py`) + Pareto stepping-stones + AST paradigm escape + graded/taint-aware SQLite memory + `ClaimLedger` + Lean 4 verification bridge (`formal_verifier.py`) + generalized BnB/Hall/valid-inequality certificates | Implemented (`0.2.0.dev1`); Lean 4 checking requires local `lean`/`lake` or container image |

## Honest boundaries

- EDA metrics are geometric proxies on fixed placements (not electrical STA or full-chip PPA).
- Live LLM discovery ablations (`H1`/`H2`) require user-configured local/remote LLM endpoints; zero-spend frozen preparation is verified for both `eda_assignment` and `weighted_vertex_cover`.
- JSP-000158 asymptotic proof drafts (`NOTE.zh-CN.md`, `FROBENIUS-OBSTRUCTIONS.zh-CN.md`, `NONSEPARABLE-AND-NONPOLYNOMIAL-OBSTRUCTIONS.zh-CN.md`) remain AI-assisted manuscripts awaiting external peer review and priority checks; no asymptotic exponent below `1/4` is claimed in this public release.
