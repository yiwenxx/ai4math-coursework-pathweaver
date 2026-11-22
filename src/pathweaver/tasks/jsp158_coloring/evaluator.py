"""Independent exhaustive and lossless-incremental AP checks; never import candidates."""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pathweaver.core.contracts import Evaluation, EvidenceLevel, validate_solution_envelope
from .certificate import check_certificate
from .model import Instance, SCHEMA_VERSION, TASK_ID, parse_instance


WITNESS_LIMIT = 8


@dataclass(frozen=True)
class PreparedJsp158Instance:
    """Precomputed 4-AP table and per-position incident index for lossless fast/delta verification."""

    instance: Instance
    aps: tuple[tuple[int, int, int, int], ...]
    incident: tuple[tuple[int, ...], ...]
    lower_bound: int


def prepare_verifier(raw: Mapping[str, Any]) -> PreparedJsp158Instance:
    instance = parse_instance(raw)
    n = instance.n
    aps: list[tuple[int, int, int, int]] = []
    incident_lists: list[list[int]] = [[] for _ in range(n)]
    for step in range(1, (n - 1) // 3 + 1):
        for start in range(n - 3 * step):
            idx = len(aps)
            quad = (start, start + step, start + 2 * step, start + 3 * step)
            aps.append(quad)
            for pos in quad:
                incident_lists[pos].append(idx)
    return PreparedJsp158Instance(
        instance=instance,
        aps=tuple(aps),
        incident=tuple(tuple(row) for row in incident_lists),
        lower_bound=3 if n >= 4 else 1,
    )


def _validate_colors_schema(instance: Instance, solution: Mapping[str, Any], lower_bound: tuple[int, ...]) -> tuple[list[int] | None, Evaluation | None]:
    n = instance.n

    def invalid(errors, diagnostics=None):
        return Evaluation(False, None, tuple(errors),
                          {"n": n, "failure_kind": "invalid_solution", **(diagnostics or {})},
                          lower_bound=lower_bound)

    payload, errors = validate_solution_envelope(
        solution, task_id=TASK_ID, instance_id=instance.instance_id, schema_version=SCHEMA_VERSION,
    )
    if payload is None:
        return None, invalid(errors)
    colors = payload.get("colors")
    if not isinstance(colors, list) or len(colors) != n:
        return None, invalid((*errors, f"solution.colors must be an array of exactly {n} labels"))
    bad_labels = [index + 1 for index, color in enumerate(colors)
                  if type(color) is not int or not 0 <= color < n]
    if bad_labels:
        errors.append(f"color labels must be integers in [0,{n - 1}]; booleans are invalid")
    if errors:
        return None, invalid(errors, {"invalid_label_positions": bad_labels[:WITNESS_LIMIT]})
    return colors, None


def evaluate_prepared(
    prepared: PreparedJsp158Instance,
    solution: Mapping[str, Any],
    *,
    parent_solution: Mapping[str, Any] | None = None,
    parent_verified: bool = False,
) -> Evaluation:
    """Verify 4-AP coloring using precomputed AP index and lossless delta checking when applicable."""
    instance = prepared.instance
    n = instance.n
    base_lb = prepared.lower_bound
    colors, err_eval = _validate_colors_schema(instance, solution, (base_lb,))
    if err_eval is not None:
        return err_eval
    assert colors is not None

    aps = prepared.aps
    ap_indices_to_check: Any = None
    verification_mode = "full"
    if parent_verified and parent_solution is not None:
        p_colors = ((parent_solution.get("solution") or {}).get("colors")
                    if isinstance(parent_solution, Mapping) else None)
        if isinstance(p_colors, list) and len(p_colors) == n and all(type(c) is int and 0 <= c < n for c in p_colors):
            changed = [i for i in range(n) if colors[i] != p_colors[i]]
            if len(changed) == 0:
                ap_indices_to_check = ()
                verification_mode = "delta_zero"
            elif 4 * len(changed) <= n:
                touched: set[int] = set()
                for pos in changed:
                    touched.update(prepared.incident[pos])
                if len(touched) < len(aps):
                    ap_indices_to_check = sorted(touched)
                    verification_mode = "delta_incremental"

    violation_count = 0
    witnesses = []
    checked = len(aps)
    quads = aps if ap_indices_to_check is None else (aps[idx] for idx in ap_indices_to_check)
    for a, b, c, d in quads:
        ca, cb, cc, cd = colors[a], colors[b], colors[c], colors[d]
        if len({ca, cb, cc, cd}) < 3:
            violation_count += 1
            if len(witnesses) < WITNESS_LIMIT:
                witnesses.append({
                    "positions": [a + 1, b + 1, c + 1, d + 1],
                    "step": b - a,
                    "colors": [ca, cb, cc, cd],
                })

    counts = Counter(colors)
    color_count = len(counts)
    diagnostics: dict[str, Any] = {
        "n": n,
        "color_count": color_count,
        "checked_progressions": checked,
        "verification_mode": verification_mode,
        "violation_count": violation_count,
        "violating_progressions": witnesses,
        "color_class_sizes": [[label, count] for label, count in sorted(counts.items())],
    }
    if violation_count:
        return Evaluation(
            False, None,
            (f"{violation_count} four-term arithmetic progressions use fewer than three colors",),
            {"n": n, "failure_kind": "invalid_solution", **diagnostics},
            lower_bound=(base_lb,),
        )

    cert_result = check_certificate(
        n, solution.get("optimality_certificate"), color_count=color_count, base_lower_bound=base_lb,
    )
    effective_lb = base_lb
    if cert_result["status"] == "verified":
        effective_lb = max(effective_lb, int(cert_result["certified_lower_bound"]))
    diagnostics["optimality_certificate"] = cert_result

    if color_count == effective_lb:
        evidence = EvidenceLevel.FINITE_OPTIMAL
    elif cert_result["status"] == "verified" and cert_result.get("evidence") == EvidenceLevel.CERTIFIED_BOUND.value:
        evidence = EvidenceLevel.CERTIFIED_BOUND
    else:
        evidence = EvidenceLevel.EXPERIMENTAL

    return Evaluation(True, (color_count,), diagnostics=diagnostics, lower_bound=(effective_lb,), evidence=evidence)


def evaluate(raw: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation:
    return evaluate_prepared(prepare_verifier(raw), solution)
