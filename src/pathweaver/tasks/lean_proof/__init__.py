"""Lean 4 formal theorem proving TaskPack."""
from collections.abc import Mapping, Sequence
from typing import Any

from pathweaver.core.contracts import Evaluation, SolveBudget

from .evaluator import evaluate
from .model import SCHEMA_VERSION, TASK_ID, generate_example, parse_instance


class LeanProofTaskPack:
    task_id = TASK_ID

    def describe(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "schema_version": SCHEMA_VERSION,
            "scope": "formal_verification",
            "status": "implemented",
            "objectives": ["min_incomplete_flag", "min_sorry_count", "min_proof_bytes"],
            "constraints": [
                "Target Lean 4 proposition is locked by host harness outside candidate namespace",
                "Zero sorry / admit / custom axiom / unsafe / native_decide / #eval",
                "Kernel #print axioms must be a subset of instance allowed_axioms",
            ],
            "decision_space": "Lean 4 helper definitions and tactic/term proof sources",
        }

    def generate(self, *, seed: int, size: int) -> Mapping[str, Any]:
        return generate_example(seed=seed, size=size)

    def validate_instance(self, instance: Mapping[str, Any]) -> Sequence[str]:
        try:
            parse_instance(instance)
        except ValueError as error:
            return (str(error),)
        return ()

    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation:
        return evaluate(instance, solution)

    def baseline(self, instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
        parsed = parse_instance(instance)
        proof = parsed.reference_proof or "first | rfl | decide | omega | simp"
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": parsed.instance_id,
            "solution": {"proof_source": proof},
            "metadata": {"strategy": "lean_baseline_tactic", "seed": budget.seed},
        }


__all__ = ["LeanProofTaskPack", "evaluate", "generate_example", "parse_instance"]
