"""Domain-neutral contracts shared by implemented TaskPacks and research code."""
from dataclasses import dataclass, field
from enum import Enum
import json
import math
from pathlib import Path
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

    def __post_init__(self) -> None:
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")
        if type(self.max_evaluations) is not int or self.max_evaluations < 1:
            raise ValueError("max_evaluations must be a positive integer")
        if (
            type(self.wall_seconds) not in (int, float)
            or not math.isfinite(self.wall_seconds)
            or self.wall_seconds <= 0
        ):
            raise ValueError("wall_seconds must be finite and positive")


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


class DiscoveryTask(Protocol):
    """Trusted discovery admission; ordered, nonnegative integer minimization."""
    task_id: str

    def prepare(self, instance: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def objective_domain(self, instance: Mapping[str, Any]) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Return sound upper bounds and divisors of every attainable objective."""
        ...
    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation: ...
    def feedback(self, evaluation: Evaluation) -> Mapping[str, Any]: ...
    def brief(self) -> str: ...


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def read_strict_json(path: str | Path) -> Any:
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


def write_json(value: Any, path: str | Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path is None:
        print(text, end="")
    else:
        Path(path).write_text(text, encoding="utf-8")
