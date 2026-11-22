"""Trusted finite instances for JSP-000158 / Erdős problem 160."""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pathweaver.core.contracts import InvalidInstanceError

TASK_ID = "jsp158_coloring"
SCHEMA_VERSION = 1
# The verifier runs on the host: bound its quadratic enumeration explicitly.
MAX_N = 4096


@dataclass(frozen=True)
class Instance:
    instance_id: str
    n: int


def parse_instance(raw: Mapping[str, Any]) -> Instance:
    """Allow top-level provenance, but admit only the full interval [1,n]."""
    errors = []
    if not isinstance(raw, Mapping):
        raise InvalidInstanceError(("instance must be an object",))
    if type(raw.get("schema_version")) is not int or raw["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if raw.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID!r}")
    identifier = raw.get("instance_id")
    if not isinstance(identifier, str) or not identifier.strip():
        errors.append("instance_id must be a nonempty string")
    data = raw.get("data")
    if not isinstance(data, Mapping):
        raise InvalidInstanceError((*errors, "data must be an object"))
    if set(data) != {"n"}:
        errors.append("data must contain exactly n; restricted progression sets are not supported")
    n = data.get("n")
    if type(n) is not int or not 1 <= n <= MAX_N:
        errors.append(f"data.n must be an integer in [1,{MAX_N}] (booleans are not integers)")
    if errors:
        raise InvalidInstanceError(errors)
    return Instance(identifier, n)


def generate(*, seed: int, size: int) -> dict[str, Any]:
    """N defines the mathematics; seed distinguishes labels, not distributions."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(size) is not int or not 1 <= size <= MAX_N:
        raise InvalidInstanceError((f"data.n must be an integer in [1,{MAX_N}] (booleans are not integers)",))
    return {"schema_version": SCHEMA_VERSION, "task_id": TASK_ID,
            "instance_id": f"jsp158-n{size}-seed{seed}", "data": {"n": size}}
