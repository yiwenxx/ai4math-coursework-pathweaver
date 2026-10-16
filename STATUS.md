# Current status

Updated: 2026-10-16 · Public development version: `0.1.0.dev1`

| Capability | State |
|---|---|
| Installable lightweight Python package and task catalogue | Available |
| EDA instance/solution formats and validity checks | Implemented; DAG, eligibility and global site capacity one |
| Independent EDA objective evaluation | Implemented; full-DAG exact lexicographic `(T,L)` |
| Seeded feasible instance generator | Implemented; runtime not exercised in the recorded checks |
| Baseline matching and local improvement | Implemented; limited fixture and public-case runs recorded |
| Path-guided minimum-cost matching | Implemented; observed on AES and Ibex; later proposal branches unexercised |
| Public DEF/LEF/Liberty import and source geometry audit | Implemented; AES and Ibex observations available |
| Bookshelf subset import and geometry audit | Available as a Python adapter; separate single-edge proxy |
| Public comparison script | Available; imports user-prepared source files and invokes each strategy once |
| Other TaskPacks and autonomous algorithm discovery | Planned |
| Execution isolation and API budget enforcement | Planned |

Recorded checks before this publication:

- Three existing handwritten instances and their baseline solutions passed independent
  evaluation, with `(T,L)` values `(5,8)`, `(20,4)` and `(9,12)`. Far-site,
  colocated-site swap and duplicate-site variants behaved as documented.
- Public AES and Ibex solutions passed independent TaskPack and source-geometry checks.
  Both strategies returned eligible capacity-one assignments with preserved HBT
  positions and zero positive-area HBT overlaps.
- The observed algorithms, inputs and outcomes are described in
  [the results](results/README.md); those observations predate the public comparison entry point.

On 2026-10-16, `python -m compileall -q src scripts` and
`python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist` passed
for the public package, producing `pathweaver_math_agent-0.1.0.dev1-py3-none-any.whl`.
No solver run, extra seed or additional benchmark is part of publication validation.
The new comparison script has not itself been run end to end; its component importer,
solvers and independent checks were exercised by the prior case workflows. To check
this entry point manually, follow [one case command](docs/eda_public_cases.md),
expect three verified rows and a generated `report.md`; exact baseline scores may
vary with machine-dependent wall-clock stopping and changed upstream inputs.

One untuned circuit supports limited strategy transfer, not general performance,
autonomous discovery or physical timing improvement. See [generalization limits](docs/generalization.md).
