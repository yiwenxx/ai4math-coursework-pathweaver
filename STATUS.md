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
| Public comparison script | One end-to-end AES run passed on existing source files; one call per strategy |
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
The initial publication validation did not rerun any solver. A subsequently requested
minimal end-to-end AES check on 2026-10-16 ran the public comparison script once,
using existing source files and seed 0, 1000 evaluations and 30 wall seconds per
strategy. It exited 0 and produced three independently verified assignments:
reference `(744915,32370920)`, baseline `(928085,35175360)` and path-matching
`(744915,32038820)`. Each covers 1492 edges with 1492 distinct eligible sites,
maximum site load one, preserved HBT positions and zero overlaps. The baseline
used 122 evaluations in 30.134280 seconds; path-matching used two in 1.803001 seconds.

No code fix, additional case, seed or retry was needed. Source/build checks were
not repeated for this documentation-only update. The public entrypoint's Ibex
path has not been run; its component behavior remains supported by the earlier
case workflow. See [the validation record](results/aes_entrypoint_validation.json)
and [reproduction steps](docs/eda_public_cases.md). Wall-clock stopping can change
evaluation counts and outcomes on another machine.

One untuned circuit supports limited strategy transfer, not general performance,
autonomous discovery or physical timing improvement. See [generalization limits](docs/generalization.md).
