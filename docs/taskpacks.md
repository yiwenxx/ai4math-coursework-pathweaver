# TaskPack interface

A task supplies the trusted mathematical definition:

| Method | Purpose |
|---|---|
| `describe()` | State the instance, solution and objective conventions |
| `generate(seed, size)` | Produce reproducible instances |
| `validate_instance(instance)` | Reject malformed or unsupported input |
| `verify(instance, solution)` | Independently check feasibility and recompute objectives |
| `baseline(instance, budget)` | Supply a reference solver |

`SolveBudget` declares wall-clock time, evaluation count and random seed. EDA solvers
implement cooperative wall and evaluation limits; these are not process isolation.

`Evaluation` contains feasibility, objective values, violations, diagnostics, an optional lower bound and evidence status. Invalid solutions have no objective tuple. Every task declares objective ordering; raw objective values from unrelated tasks are not comparable.

EDA is the first implementation. See [its format and ordering](eda_assignment.md)
and `src/pathweaver/core/contracts.py` for the exported types. EDA's default
`baseline()` remains the original solver; the CLI exposes `path-matching` separately.
The catalogue contains only implemented public tasks.
