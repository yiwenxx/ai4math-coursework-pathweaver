# EDA examples

These small instances and solutions were handwritten with manually derived objectives.
The provenance strings describe their original creation; subsequent verification is
recorded below. They are examples, not a broad benchmark dataset.

| Instance / corresponding `_solution.json` | `(T,L)` | Purpose |
|---|---|---|
| `eda_assignment/example.json` | `(5,8)` | Eligible assignment to distinct global sites |
| `eda_assignment/fixed_path.json` | `(20,4)` | A fixed path determines T and L breaks ties |
| `eda_assignment/tied_sites.json` | `(9,12)` | Different site IDs at the same coordinates retain separate capacity |

On 2026-10-14, each handwritten solution and one baseline solution per instance
passed independent verification and attained both lower bounds. The following
variants were also checked: moving to the far site in `fixed_path` produced `(20,8)`;
swapping the two colocated sites preserved `(9,12)`; reusing one site ID was rejected.
This establishes the stated results for these instances, not general solver quality.

```bash
pathweaver eda verify benchmarks/eda_assignment/fixed_path.json benchmarks/eda_assignment/fixed_path_solution.json
```

`expected_objectives` is explanatory metadata and is ignored by the verifier.
The public circuit data are obtained separately; see [input preparation](../docs/eda_public_cases.md).
