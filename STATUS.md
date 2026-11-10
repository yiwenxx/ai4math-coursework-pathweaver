# Current status

Updated: 2026-11-11 · Public development version: `0.1.0.dev1`

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
| Public comparison script | One end-to-end run each on existing AES and Ibex files passed; one call per strategy per case |
| JSP-000158 research notes and finite coloring artifacts | Complete proof drafts for quantitative refinement and restricted Frobenius-family obstructions; external correctness and novelty unconfirmed; original finite tables previously checked |
| Other public TaskPacks and autonomous algorithm discovery | Planned |
| Execution isolation and API budget enforcement | Planned |

On 2026-11-11, the [Frobenius obstruction note](research/jsp158/FROBENIUS-OBSTRUCTIONS.zh-CN.md)
adds full proofs for a precisely defined cubic-norm coloring family with arbitrary
Frobenius and linear measurement coefficients. Avoiding ABBA forces prime-field
quadratic coefficients and base dimension at most two. A sufficiently large fixed
field excludes every positive base dimension; a separate single-term result applies
when e>=2j+1. Exact hypotheses, degenerate cases and primary sources are in the note.
An extension gives ed<=2dim(W) for arbitrary additive measurement spaces,
without a minimum-rank assumption or restriction on q modulo 3. Classical
exponential-sum estimates supply the missing low-rank case. For arbitrary
linearized coefficients of degree at most p^h, h>=2 and e>=2h+1, every positive
base dimension is excluded, including q=7^5 with three independent terms.
These statements have received direct AI-assisted mathematical review, without
external expert or formal certification. They are not arbitrary-coloring lower bounds
and do not improve the leading exponent below 1/4; priority remains unconfirmed.

The q=121 candidate diagnostic reported full value-set coverage for 40,656 normalized
parameter groups. It has no trusted independent verification or certificate and does
not establish the remaining d=1 or d=2 cases. This update changes documentation only;
software sources, finite arrays and their verifier are unchanged. No additional local
compilation, build, model request or mathematical rerun was needed for publication.

On 2026-11-02, the public repository added [JSP-000158 research note v0.1.0](research/jsp158/NOTE.zh-CN.md).
It includes a complete AI-assisted proof draft, explicit literature attribution, five finite
coloring arrays and the known modulo-22 ABBA template. These finite constructions have prior
exhaustive verification records. The new standalone recomputation script is compile-checked;
no solver, model call or successful finite verification is repeated for this publication.
The note does not certify novelty or improve the known leading exponent 1/4.
The research-note version is separate from the unchanged software package version.

Publication validation on 2026-11-02: one `python -m compileall -q src scripts`
and one offline `python -m pip wheel . --no-deps --no-build-isolation --no-index --wheel-dir dist`
completed successfully. No new test suite or repeated mathematical verification was run.

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

A separate requested Ibex check on the same date ran the same public entrypoint
once on existing files with the same budget. It exited 0 with reference
`(1663875,47974340)`, baseline `(1835280,49687230)` and path-matching
`(1663875,47840820)`. Each covers all 1592 data-graph cross edges with 1592 distinct
eligible sites and maximum load one. All 1599 physical HBTs retain their position
multiset with zero overlaps; seven fixed control HBTs have no data-graph cross edge.
The baseline used 134 evaluations in 30.242825 seconds; path-matching used two
in 1.310219 seconds. Both independent objective calculations agree for every row.

Neither check required a code fix, extra seed or retry. The Ibex check did not
rerun AES. No additional local build was needed for these documentation-only
updates. See the [AES record](results/aes_entrypoint_validation.json),
[Ibex record](results/ibex_entrypoint_validation.json) and
[reproduction steps](docs/eda_public_cases.md). Wall-clock stopping can change
evaluation counts and outcomes on another machine. Replaying these existing
cases adds no new generalization sample.

One untuned circuit supports limited strategy transfer, not general performance,
autonomous discovery or physical timing improvement. See [generalization limits](docs/generalization.md).
