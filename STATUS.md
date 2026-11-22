# Current status

Updated: 2026-11-21 · Public development version: `0.2.0.dev1`

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
- JSP-000158 asymptotic proof drafts (`NOTE.zh-CN.md`, `FROBENIUS-OBSTRUCTIONS.zh-CN.md`) remain AI-assisted candidate manuscripts awaiting external peer review, formalization, and priority checks; no exponent below `1/4` is claimed.
