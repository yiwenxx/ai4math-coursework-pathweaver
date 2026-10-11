# TaskPack interface

A task supplies the trusted mathematical definition:

| Method | Purpose |
|---|---|
| `describe()` | State the instance, solution and objective conventions |
| `generate(seed, size)` | Produce reproducible instances |
| `validate_instance(instance)` | Reject malformed or unsupported input |
| `verify(instance, solution)` | Independently check feasibility and recompute objectives |
| `baseline(instance, budget)` | Supply a reference solver |

`SolveBudget` declares wall-clock time, evaluation count and random seed. It is a data contract; the current scaffold does not enforce resource limits.

`Evaluation` contains feasibility, objective values, violations, diagnostics, an optional lower bound and evidence status. Invalid solutions have no objective tuple. Every task declares objective ordering; raw objective values from unrelated tasks are not comparable.

The catalogue currently has no public task implementations. See `src/pathweaver/core/contracts.py` for the exported types.
