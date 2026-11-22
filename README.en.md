# PathWeaver

**A Streamlined, Verifiable Core for AI4Math Algorithm Discovery and Mathematical Research (`0.2.0.dev1`).**

[中文 README](README.md) · [Status](STATUS.md) · [EDA Spec & Certificates](docs/eda_assignment.md) · [Public Circuits](docs/eda_public_cases.md) · [Lean 4 Verification](docs/lean_proof.md) · [Results](results/README.md) · [Generalization Limits](docs/generalization.md) · [JSP-000158 Research](research/jsp158/README.md)

---

## Streamlined Core (Zero Third-Party Runtime Dependencies)

PathWeaver strips away heavyweight workflow ceremony (Markdown/Git vaults, illustrative demos, offline stub planners) and retains five sharp, zero-bloat pillars built directly for **discovering and independently verifying innovative algorithms and mathematical claims**:

1. **EDA Path-Coupled Assignment (`pathweaver eda`)**: Exact lexicographic `(T, L)` DAG optimization, `path-matching`, **solver-independent Hungarian primal–dual & Hall-conflict `finite_optimal` certificates (`--require-certificate`)**, Open3DBench AES/Ibex importers, and capacity-gap diagnostics.
2. **Weighted Minimum Vertex Cover (`pathweaver wvc`)**: Cross-structure transfer TaskPack with independent verifier, valid-inequality dual lower bounds (edges, odd cycles, cliques), weighted greedy + local search baseline, exact tiny branch-and-bound solver with `bnb_proof_tree` certificates, and `DiscoveryTask` adapter.
3. **JSP-000158 / Erdős #160 (`pathweaver jsp158`)**: Exhaustive & incremental 4-AP verifier, legal seed, **independently verified `q=121` mixed-curve certificate (`scripts/certify_q121.py`, 40,656 groups / 4,919,376 equations)**, small finite-field counterexample probe (`ff_probe.py`), and candidate proof manuscripts.
4. **Lean 4 Formal Verification (`pathweaver lean`, `formal/`)**: Zero-Mathlib pure Lean 4 library `PathWeaverFormal` (`v4.36.0`), EDA/WVC/JSP-000158 Lean certificate exporters, statement-locked `lean_proof` TaskPack, and `#print axioms` kernel audit.
5. **Minimal Discovery & Evidence Core**: Lossless integer-tuple + Pareto stepping-stone AdaEvolve ordering (`exact_ordering.py`), AST paradigm escape (`strategy_escape.py`), graded/taint-aware SQLite memory (`context_adapter.py` + `store.py`/`retrieval.py`), and impact-weighted `ClaimLedger` (`pathweaver claims`).

---

## Quick Start

```bash
python -m pip install -e .
pathweaver info
pathweaver tasks

pathweaver eda solve benchmarks/eda_assignment/example.json --strategy path-matching --output sol.json
pathweaver eda verify benchmarks/eda_assignment/example.json sol.json --require-certificate

pathweaver wvc verify benchmarks/weighted_vertex_cover/example.json benchmarks/weighted_vertex_cover/example_solution.json
python scripts/verify_jsp158_artifacts.py
python scripts/certify_q121.py verify results/q121_mixed_curve_certificate.json
```

See [STATUS.md](STATUS.md) and [docs/generalization.md](docs/generalization.md) for verified highlights and honest boundaries. Licensed under Apache-2.0.
