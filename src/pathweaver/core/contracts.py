"""Domain-neutral contracts, JSON/hash primitives, and envelope validators."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4


class IsolationError(RuntimeError):
    """Raised when an execution sandbox or required formal verifier backend is unavailable."""


class InvalidInstanceError(ValueError):
    """Raised when a task instance violates its structural or schema contract."""

    def __init__(self, violations: Sequence[str]):
        self.violations = tuple(violations)
        super().__init__("; ".join(self.violations))


class EvidenceLevel(str, Enum):
    HYPOTHESIS = "hypothesis"
    UNVERIFIED = "unverified"
    EXPERIMENTAL = "experimental"
    COUNTEREXAMPLE = "counterexample"
    CERTIFIED_BOUND = "certified_bound"
    FINITE_OPTIMAL = "finite_optimal"
    HUMAN_PROOF = "human_proof"
    FORMAL_VERIFIED = "formal_verified"


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
    """Trusted discovery admission; ordered, nonnegative integer minimization.

    Optional TaskPack discovery hooks supported by the shared harness:
    - ``prepare_verifier(instance)`` / ``verify_prepared(prepared, solution, *, parent_solution=None)``
    - ``paradigm_catalog()``
    - ``reduce_instance(instance, evaluation, *, max_size=...)``
    - ``subset_elements(instance)`` / ``rebuild_from_subset(instance, kept)`` (for ``ddmin``)
    - ``permute_instance(instance, *, seed=...)`` (for isomorphic metamorphic checks)
    - ``generate_adversarial_instances(*, seed=..., count=...)``
    - ``calibrate_instance_delays(instance, edge_measurements)``
    - ``certificate(instance, solution, evaluation)``
    Constructive two-phase search tasks also implement ``ConstructiveWitnessTask`` in ``core/constructive.py``.
    """
    task_id: str

    def prepare(self, instance: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def objective_domain(self, instance: Mapping[str, Any]) -> tuple[tuple[int, ...], tuple[int, ...]]:
        """Return sound upper bounds and divisors of every attainable objective."""
        ...
    def verify(self, instance: Mapping[str, Any], solution: Mapping[str, Any]) -> Evaluation: ...
    def feedback(self, evaluation: Evaluation) -> Mapping[str, Any]: ...
    def brief(self) -> str: ...


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def require_nonneg_int(value: Any, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def validate_instance_envelope(
    raw: Any,
    *,
    task_id: str,
    schema_version: int = 1,
) -> tuple[str, Mapping[str, Any]]:
    """Validate common `(schema_version, task_id, instance_id, data)` instance envelope."""
    if not isinstance(raw, Mapping):
        raise ValueError("instance must be a JSON object")
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != schema_version:
        raise ValueError(f"schema_version must be {schema_version}")
    if raw.get("task_id") != task_id:
        raise ValueError(f"task_id must be {task_id!r}")
    instance_id = require_text(raw.get("instance_id"), "instance_id")
    data = raw.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("data must be an object")
    return instance_id, data


def validate_solution_envelope(
    solution: Any,
    *,
    task_id: str,
    instance_id: str,
    schema_version: int = 1,
) -> tuple[Mapping[str, Any] | None, list[str]]:
    """Validate common solution envelope and return `(payload_or_None, violations)`."""
    if not isinstance(solution, Mapping):
        return None, ["solution must be an object"]
    violations: list[str] = []
    version = solution.get("schema_version")
    if type(version) is not int or version != schema_version:
        violations.append(f"solution.schema_version must be {schema_version}")
    if solution.get("task_id") != task_id:
        violations.append(f"solution.task_id must be {task_id!r}")
    if solution.get("instance_id") != instance_id:
        violations.append("solution.instance_id does not match the instance")
    payload = solution.get("solution")
    if not isinstance(payload, Mapping):
        violations.append("solution.solution must be an object")
        return None, violations
    return payload, violations


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_unique_object,
        parse_constant=_reject_constant,
    )


def read_strict_json(path: str | Path) -> Any:
    return parse_strict_json(Path(path).read_text(encoding="utf-8-sig"))


def write_json(value: Any, path: str | Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path is None:
        print(text, end="")
    else:
        Path(path).write_text(text, encoding="utf-8", newline="\n")


def atomic_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_json(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
