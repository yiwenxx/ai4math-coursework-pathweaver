"""Domain-neutral metamorphic invariance verification and empirical scaling estimation."""
from collections.abc import Callable, Mapping, Sequence
import math
from typing import Any


def _extract_eval_fields(eval_obj: Any) -> tuple[bool, list[int] | None, list[str], tuple[int, ...] | None]:
    if isinstance(eval_obj, Mapping):
        inner = eval_obj.get("evaluation") if isinstance(eval_obj.get("evaluation"), Mapping) else eval_obj
        feasible = bool(inner.get("feasible", False))
        raw_objs = inner.get("objectives")
        objs = [int(v) for v in raw_objs] if isinstance(raw_objs, (list, tuple)) else None
        violations = [str(v) for v in (inner.get("violations") or ())]
        raw_lb = inner.get("lower_bound")
        lb = tuple(int(v) for v in raw_lb) if isinstance(raw_lb, (list, tuple)) and raw_lb else None
        return feasible, objs, violations, lb
    feasible = bool(getattr(eval_obj, "feasible", False))
    raw_objs = getattr(eval_obj, "objectives", None)
    objs = [int(v) for v in raw_objs] if isinstance(raw_objs, (list, tuple)) else None
    violations = [str(v) for v in (getattr(eval_obj, "violations", ()) or ())]
    raw_lb = getattr(eval_obj, "lower_bound", None)
    lb = tuple(int(v) for v in raw_lb) if isinstance(raw_lb, (list, tuple)) and raw_lb else None
    return feasible, objs, violations, lb


def verify_metamorphic_invariance(
    task: Any,
    run_fn: Callable[[Mapping[str, Any]], Any],
    instance: Mapping[str, Any],
    baseline_eval: Mapping[str, Any] | Any,
    *,
    seed: int = 991,
    rel_tol: float = 0.15,
) -> dict[str, Any]:
    """Verify feasibility and non-degradation on an isomorphic instance permutation."""
    permute_fn = getattr(task, "permute_instance", None)
    if not callable(permute_fn):
        return {
            "passed": False,
            "reason": "task does not define permute_instance",
            "permuted_objectives": None,
        }

    permuted_inst = permute_fn(instance, seed=seed)
    try:
        run_out = run_fn(permuted_inst)
    except Exception as error:
        return {
            "passed": False,
            "reason": f"metamorphic execution error: {type(error).__name__}: {error}",
            "permuted_objectives": None,
        }

    eval_obj: Any
    if isinstance(run_out, tuple) and len(run_out) == 2:
        solution, eval_obj = run_out
        if eval_obj is None and isinstance(solution, Mapping):
            eval_obj = task.verify(permuted_inst, solution)
    elif isinstance(run_out, Mapping) and "solution" in run_out and "feasible" not in run_out and "evaluation" not in run_out:
        eval_obj = task.verify(permuted_inst, run_out)
    else:
        eval_obj = run_out

    feasible, perm_objs, violations, perm_lb = _extract_eval_fields(eval_obj)
    if not feasible or perm_objs is None:
        detail = "; ".join(violations[:4]) or "missing objective tuple"
        return {
            "passed": False,
            "reason": f"infeasible on isomorphic permutation: {detail}",
            "permuted_objectives": perm_objs,
        }

    if perm_lb is not None and len(perm_lb) == len(perm_objs):
        if perm_objs[0] < perm_lb[0]:
            return {
                "passed": False,
                "reason": f"structural lower-bound inconsistency: {perm_objs} < {list(perm_lb)}",
                "permuted_objectives": perm_objs,
            }

    base_feasible, base_objs, _, _ = _extract_eval_fields(baseline_eval)
    if base_feasible and base_objs is not None:
        if len(perm_objs) != len(base_objs):
            return {
                "passed": False,
                "reason": f"objective dimensionality mismatch: baseline={len(base_objs)}, permuted={len(perm_objs)}",
                "permuted_objectives": perm_objs,
            }
        identical_data = permuted_inst.get("data") == instance.get("data")
        if identical_data:
            if tuple(perm_objs) > tuple(base_objs):
                return {
                    "passed": False,
                    "reason": f"id-memorization suspected: degraded from {base_objs} to {perm_objs} on identical data",
                    "permuted_objectives": perm_objs,
                }
        else:
            allowed_primary = base_objs[0] * (1.0 + max(0.0, float(rel_tol)))
            if perm_objs[0] > allowed_primary:
                return {
                    "passed": False,
                    "reason": (
                        f"metamorphic degradation on primary objective: "
                        f"baseline={base_objs}, permuted={perm_objs}"
                    ),
                    "permuted_objectives": perm_objs,
                }

    return {
        "passed": True,
        "reason": "metamorphic invariance verified",
        "permuted_objectives": perm_objs,
    }


def estimate_empirical_scaling(
    sizes: Sequence[int | float],
    wall_times: Sequence[float],
) -> dict[str, Any]:
    """Fit log(T) ~= alpha * log(N) + c across instance sizes and wall-clock times."""
    if len(sizes) != len(wall_times):
        raise ValueError("sizes and wall_times must have the same length")

    xs: list[float] = []
    ys: list[float] = []
    for raw_n, raw_t in zip(sizes, wall_times):
        n_val = float(raw_n)
        t_val = float(raw_t)
        if not (math.isfinite(n_val) and math.isfinite(t_val)) or n_val <= 0.0:
            continue
        xs.append(math.log(n_val))
        ys.append(math.log(max(1e-6, t_val)))

    m = len(xs)
    if m < 2:
        return {"alpha": None, "r2": None, "samples": m, "warning": "insufficient_samples"}

    mean_x = sum(xs) / m
    mean_y = sum(ys) / m
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx <= 1e-12:
        return {"alpha": None, "r2": None, "samples": m, "warning": "identical_instance_sizes"}

    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    syy = sum((y - mean_y) ** 2 for y in ys)
    alpha = sxy / sxx
    intercept = mean_y - alpha * mean_x

    if syy <= 1e-12:
        r2 = 1.0
    else:
        ss_res = sum((y - (alpha * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r2 = max(0.0, min(1.0, 1.0 - ss_res / syy))

    warning = f"super_quadratic_scaling: empirical exponent alpha={alpha:.2f}" if alpha > 2.5 else ""
    return {
        "alpha": round(alpha, 6),
        "r2": round(r2, 6),
        "samples": m,
        "warning": warning,
    }
