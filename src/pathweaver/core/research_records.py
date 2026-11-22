"""Domain-neutral, JSON-serializable research records.

Labels describe the caller's evidence; they are not verification certificates.
Only a trusted evaluator should submit records marked ``verified``.
"""
from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from pathweaver.core.contracts import canonical_json, require_text


KINDS = {"run", "attempt", "hypothesis", "lesson", "route", "checkpoint", "invalidation"}
IMMUTABLE_KINDS = {"run", "attempt", "checkpoint", "invalidation"}
OUTCOMES = {"feasible", "invalid", "malformed", "timeout", "exception"}
VERIFICATIONS = {"verified", "unverified", "illustrative"}
INVALIDATION_SEVERITIES = {"fatal", "boundary_drift", "superseded"}
CONTEXT_EXPOSURE_KINDS = {"attempt", "hypothesis", "lesson", "route"}
REF_FIELDS = {
    "attempt": ("parent_id", "hypothesis_id", "context_exposure_ids"),
    "hypothesis": ("support_ids", "contradiction_ids", "context_exposure_ids"),
    "lesson": ("support_ids", "contradiction_ids", "context_exposure_ids"),
    "route": ("hypothesis_id", "evidence_ids", "context_exposure_ids"),
    "checkpoint": ("evidence_ids",),
    "invalidation": ("target_id", "replacement_id"),
}


def require_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
        raise ValueError("Record IDs must contain 1–128 ASCII identifier characters")
    return value


def require_integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer")
    return value


def require_nonnegative(value: Any, name: str) -> None:
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")


@dataclass(frozen=True)
class ResearchScope:
    task_id: str
    task_version: str
    verifier_version: str
    fitness_dataset_id: str

    def as_dict(self) -> dict[str, str]:
        return dict(vars(self))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResearchScope":
        scope = cls(**dict(data))
        for name in ("task_id", "task_version", "verifier_version", "fitness_dataset_id"):
            require_text(getattr(scope, name), name)
        return scope


@dataclass(frozen=True)
class ResearchEvent:
    sequence: int
    record_id: str
    kind: str
    run_id: str
    revision: int
    created_at: str
    payload: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return dict(vars(self))

    @property
    def references(self) -> tuple[str, ...]:
        refs: list[str] = []
        for field in REF_FIELDS.get(self.kind, ()):
            value = self.payload.get(field)
            if value:
                refs.extend(value if isinstance(value, list) else [value])
        return tuple(dict.fromkeys(refs))

    @property
    def dependencies(self) -> tuple[str, ...]:
        # A verified child result remains usable even if its parent's result is revoked.
        # Lineage, contradictions, and implicit prompt-window exposure have distinct meanings.
        if self.kind in {"attempt", "invalidation"}:
            return ()
        fields = {
            "hypothesis": ("support_ids",),
            "lesson": ("support_ids",),
            "route": ("hypothesis_id", "evidence_ids"),
            "checkpoint": ("evidence_ids",),
        }.get(self.kind, ())
        refs: list[str] = []
        for field in fields:
            value = self.payload.get(field)
            if value:
                refs.extend(value if isinstance(value, list) else [value])
        return tuple(dict.fromkeys(refs))

    @property
    def support_dependencies(self) -> tuple[str, ...]:
        if self.kind in {"hypothesis", "lesson"}:
            return tuple(dict.fromkeys(self.payload.get("support_ids") or ()))
        if self.kind == "route":
            return self.dependencies
        return ()

    @property
    def contradiction_dependencies(self) -> tuple[str, ...]:
        if self.kind in {"hypothesis", "lesson"}:
            return tuple(dict.fromkeys(self.payload.get("contradiction_ids") or ()))
        return ()

    @property
    def context_exposures(self) -> tuple[str, ...]:
        if self.kind in CONTEXT_EXPOSURE_KINDS:
            return tuple(dict.fromkeys(self.payload.get("context_exposure_ids") or ()))
        return ()


def validate_payload(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"Unknown research record kind: {kind}")
    if not isinstance(payload, Mapping):
        raise ValueError("Record payload must be an object")
    data = dict(payload)
    canonical_json(data)
    if "split" in data and data["split"] != "train":
        raise ValueError("Research memory accepts only training evidence")
    tags = data.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
        raise ValueError("tags must be a list of nonempty strings")
    for field in REF_FIELDS.get(kind, ()):
        value = data.get(field)
        if value is not None:
            if field.endswith("_ids"):
                if not isinstance(value, list):
                    raise ValueError(f"{field} must be a list")
                for ref in value:
                    require_id(ref)
            else:
                require_id(value)
    if "context_through_sequence" in data and data["context_through_sequence"] is not None:
        seq = require_integer(data["context_through_sequence"], "context_through_sequence")
        if seq < 0:
            raise ValueError("context_through_sequence must be nonnegative")
    if kind == "run":
        ResearchScope.from_dict(data.get("scope", {}))
        require_integer(data.get("seed"), "seed")
        if data.get("provenance") not in {"experiment", "illustrative"}:
            raise ValueError("Run provenance must be experiment or illustrative")
        directions = data.get("objective_directions")
        if not isinstance(directions, list) or not directions or any(d not in {"min", "max"} for d in directions):
            raise ValueError("Declare lexicographic objective_directions, using min/max")
    elif kind == "attempt":
        for field in ("candidate_id", "config_id", "dataset_id"):
            require_text(data.get(field), field)
        if data.get("instance_id") is not None:
            require_text(data["instance_id"], "instance_id")
        require_integer(data.get("seed"), "seed")
        if data.get("split") != "train":
            raise ValueError("Attempts must explicitly declare split=train")
        if data.get("dataset_role", "fitness") not in {"fitness", "diagnostic"}:
            raise ValueError("dataset_role must be fitness or diagnostic")
        if data.get("outcome") not in OUTCOMES or data.get("verification") not in VERIFICATIONS:
            raise ValueError("Declare a known outcome and verification status")
        objectives = data.get("objectives")
        if data["outcome"] == "feasible":
            if not isinstance(objectives, list) or not objectives:
                raise ValueError("Feasible attempts need integer objectives")
            for value in objectives:
                require_integer(value, "objective")
        elif objectives is not None:
            raise ValueError("Failed attempts cannot have objective values")
        require_nonnegative(data.get("wall_seconds"), "wall_seconds")
        if "api_cost" in data:
            require_nonnegative(data["api_cost"], "api_cost")
            require_text(data.get("currency"), "currency")
        if not isinstance(data.get("diagnostics", {}), dict):
            raise ValueError("diagnostics must be an object")
        require_text(data.get("source_ref"), "source_ref")
    elif kind in {"hypothesis", "lesson"}:
        require_text(data.get("statement"), "statement")
        if kind == "hypothesis":
            require_text(data.get("test_plan"), "test_plan")
            if data.get("state") not in {"open", "supported", "refuted", "inconclusive"}:
                raise ValueError("Unknown hypothesis state")
        else:
            require_text(data.get("conditions"), "conditions")
            if data.get("state") not in {"provisional", "experimental", "retired"}:
                raise ValueError("Unknown lesson state")
            if not data.get("support_ids"):
                raise ValueError("Lessons must cite at least one supporting attempt")
    elif kind == "route":
        require_text(data.get("rationale"), "rationale")
        if data.get("action") not in {"variant", "diagnose", "controlled_compare", "scale", "restart"}:
            raise ValueError("Unknown route action")
        if data.get("state") not in {"queued", "active", "done", "paused"}:
            raise ValueError("Unknown route state")
    elif kind == "checkpoint":
        require_integer(data.get("through_sequence"), "through_sequence")
        require_text(data.get("trigger"), "trigger")
    elif kind == "invalidation":
        require_id(data.get("target_id"))
        require_text(data.get("reason"), "reason")
        severity = data.get("severity", "fatal")
        if severity not in INVALIDATION_SEVERITIES:
            raise ValueError(f"invalidation severity must be one of {sorted(INVALIDATION_SEVERITIES)}")
        if data.get("replacement_id") is not None:
            require_id(data["replacement_id"])
    return data
