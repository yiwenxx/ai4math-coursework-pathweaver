"""Domain-neutral contracts; implementations are milestone work."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


class EvidenceLevel(str, Enum):
    HYPOTHESIS = "hypothesis"
    EXPERIMENTAL = "experimental"
    COUNTEREXAMPLE = "counterexample"
    FINITE_OPTIMAL = "finite_optimal"
    HUMAN_PROOF = "human_proof"


@dataclass(frozen=True)
class SolveBudget:
    wall_seconds: float
    max_evaluations: int
    seed: int


@dataclass(frozen=True)
class Evaluation:
    feasible: bool
    objectives: tuple[int, ...] | None
    violations: tuple[str, ...] = ()
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    lower_bound: tuple[int, ...] | None = None
    evidence: EvidenceLevel = EvidenceLevel.EXPERIMENTAL


class TaskPack(Protocol):
    """Trusted task implementation; candidate solvers cannot change it.

    Objectives use the task's declared ordering. Invalid solutions have no
    objective tuple. Raw scores from different tasks are not comparable.
    """
    task_id: str

    def describe(self) -> Mapping[str, Any]: ...
    def generate(self, *, seed: int, size: int) -> Mapping[str, Any]: ...
    def validate_instance(self, instance: Mapping[str, Any]) -> Sequence[str]: ...
    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation: ...
    def baseline(self, instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]: ...
