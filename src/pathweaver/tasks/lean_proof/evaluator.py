"""Host-side Lean 4 kernel evaluator with statement locking and axiom audit."""
from collections.abc import Mapping
import re
from typing import Any

from pathweaver.core.contracts import Evaluation, EvidenceLevel, validate_solution_envelope
from pathweaver.research.formal_verifier import (
    _strip_lean_comments_and_strings,
    build_locked_lean_module,
    verify_formal_proof,
)

from .model import LeanProofInstance, SCHEMA_VERSION, TASK_ID, parse_instance

MAX_SORRY_BOUND = 1000
MAX_PROOF_BYTES = 1_000_000


class LeanBackendUnavailableError(RuntimeError):
    """Raised during discovery when the host Lean 4 / Lake backend is unavailable."""


def evaluate_lean_source(
    raw_instance: Mapping[str, Any] | LeanProofInstance,
    proof_source: str,
    *,
    allow_sorry_search: bool = False,
    wall_seconds: float = 60.0,
    docker_image: str | None = None,
    use_warm_server: bool = False,
    auto_repair: bool = False,
    raise_on_unavailable: bool = False,
) -> Evaluation:
    """Lock the target statement, compile via Lean 4 kernel, and return structured Evaluation."""
    instance = raw_instance if isinstance(raw_instance, LeanProofInstance) else parse_instance(raw_instance)
    lower_bound = (0, 0, 1)

    if not isinstance(proof_source, str) or not proof_source.strip():
        return Evaluation(
            feasible=False,
            objectives=None,
            violations=("Lean proof source must be nonempty text",),
            diagnostics={"theorem_name": instance.theorem_name, "formal_verified": False},
            lower_bound=lower_bound,
            evidence=EvidenceLevel.UNVERIFIED,
        )

    try:
        wrapped = build_locked_lean_module(
            instance.theorem_name,
            instance.statement,
            proof_source,
            imports=instance.imports,
            preamble=instance.preamble,
            allow_sorry=allow_sorry_search,
        )
    except ValueError as error:
        return Evaluation(
            feasible=False,
            objectives=None,
            violations=(str(error),),
            diagnostics={
                "theorem_name": instance.theorem_name,
                "formal_verified": False,
                "soundness_errors": [str(error)],
            },
            lower_bound=lower_bound,
            evidence=EvidenceLevel.UNVERIFIED,
        )

    verdict = verify_formal_proof(
        wrapped,
        backend="lean4",
        theorem_name="_pathweaver_verified_target",
        project_dir=instance.project_dir,
        docker_image=docker_image,
        timeout_seconds=wall_seconds,
        allowed_axioms=frozenset(instance.allowed_axioms),
        allow_partial_sorry=allow_sorry_search,
        use_warm_server=(use_warm_server and docker_image is None),
    )

    if verdict.status == "backend_unavailable":
        if raise_on_unavailable:
            raise LeanBackendUnavailableError(verdict.compiler_output or "Lean 4 executable unavailable")
        return Evaluation(
            feasible=False,
            objectives=None,
            violations=(verdict.compiler_output or "Lean 4 backend unavailable",),
            diagnostics={
                "theorem_name": instance.theorem_name,
                "formal_verified": False,
                "status": verdict.status,
            },
            lower_bound=lower_bound,
            evidence=EvidenceLevel.UNVERIFIED,
        )

    repaired = False
    if auto_repair and docker_image is None and verdict.status in {"incomplete_sorry", "failed"}:
        from pathweaver.research.lean_repair import repair_lean_proof

        repair_res = repair_lean_proof(
            instance,
            proof_source,
            wall_seconds=min(8.0, max(1.0, wall_seconds * 0.4)),
            use_warm_server=use_warm_server,
        )
        repair_verdict = repair_res.get("verdict")
        if repair_res.get("repaired") and repair_verdict is not None:
            adopt = (
                repair_verdict.status == "verified"
                or (
                    allow_sorry_search
                    and repair_verdict.status == "incomplete_sorry"
                    and (
                        verdict.status == "failed"
                        or repair_verdict.sorry_count < verdict.sorry_count
                    )
                )
            )
            if adopt:
                proof_source = str(repair_res["repaired_source"])
                verdict = repair_verdict
                repaired = True

    diag_messages = [dict(item) for item in verdict.diagnostics[:8]]
    base_diag: dict[str, Any] = {
        "theorem_name": instance.theorem_name,
        "status": verdict.status,
        "source_sha256": verdict.source_sha256,
        "axioms": list(verdict.axioms),
        "sorry_count": verdict.sorry_count,
        "error_count": verdict.error_count,
        "wall_seconds": verdict.wall_seconds,
        "lean_messages": diag_messages,
        "compiler_output": verdict.compiler_output[:2000],
    }
    if repaired:
        base_diag["repaired"] = True
        base_diag["repaired_source"] = proof_source

    if verdict.status == "verified":
        proof_bytes = min(MAX_PROOF_BYTES, len(proof_source.encode("utf-8")))
        base_diag["formal_verified"] = True
        return Evaluation(
            feasible=True,
            objectives=(0, 0, proof_bytes),
            violations=(),
            diagnostics=base_diag,
            lower_bound=lower_bound,
            evidence=EvidenceLevel.FORMAL_VERIFIED,
        )

    if allow_sorry_search and verdict.status == "incomplete_sorry":
        cleaned = _strip_lean_comments_and_strings(proof_source)
        total_steps = len(re.findall(r"\b(?:have|lemma)\b", cleaned))
        verified_steps = max(0, total_steps - verdict.sorry_count)
        base_sketch = min(64, MAX_SORRY_BOUND // 2)
        remaining_burden = max(
            1,
            min(
                MAX_SORRY_BOUND,
                base_sketch + verdict.sorry_count * 4 - min(base_sketch - 1, verified_steps * 6),
            ),
        )
        proof_bytes = min(MAX_PROOF_BYTES, len(proof_source.encode("utf-8")))
        base_diag["formal_verified"] = False
        base_diag["verified_steps"] = verified_steps
        base_diag["remaining_burden"] = remaining_burden
        return Evaluation(
            feasible=True,
            objectives=(1, remaining_burden, proof_bytes),
            violations=(),
            diagnostics=base_diag,
            lower_bound=lower_bound,
            evidence=EvidenceLevel.HYPOTHESIS,
        )

    violations: list[str] = list(verdict.soundness_errors)
    for item in verdict.diagnostics:
        if item.get("severity") == "error":
            loc = f"L{item.get('line')}:C{item.get('column')}" if item.get("line") else "lean"
            violations.append(f"{loc}: {item.get('message', '')[:300]}")
    if not violations:
        violations.append(verdict.compiler_output[:400] or f"Lean verification failed ({verdict.status})")

    base_diag["formal_verified"] = False
    return Evaluation(
        feasible=False,
        objectives=None,
        violations=tuple(violations[:8]),
        diagnostics=base_diag,
        lower_bound=lower_bound,
        evidence=EvidenceLevel.UNVERIFIED,
    )


def evaluate(raw_instance: Mapping[str, Any], solution: Any) -> Evaluation:
    """Strict standalone verifier for serialized JSON Lean proof solutions (never allows `sorry`)."""
    instance = parse_instance(raw_instance)
    payload, violations = validate_solution_envelope(
        solution, task_id=TASK_ID, instance_id=instance.instance_id, schema_version=SCHEMA_VERSION,
    )
    if payload is None or not isinstance(payload.get("proof_source"), str):
        if payload is not None:
            violations.append("solution.solution.proof_source must be a Lean 4 source string")
        return Evaluation(False, None, tuple(violations), evidence=EvidenceLevel.UNVERIFIED)
    if violations:
        return Evaluation(False, None, tuple(violations), evidence=EvidenceLevel.UNVERIFIED)
    return evaluate_lean_source(instance, payload["proof_source"], allow_sorry_search=False)
