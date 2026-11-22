"""Trusted instance representation and validation for Lean 4 theorem proving."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from pathweaver.core.contracts import require_text, validate_instance_envelope
from pathweaver.research.formal_verifier import ALLOWED_LEAN_AXIOMS

TASK_ID = "lean_proof"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LeanProofInstance:
    instance_id: str
    theorem_name: str
    imports: tuple[str, ...]
    preamble: str
    statement: str
    allowed_axioms: tuple[str, ...]
    allow_sorry_seed: bool
    project_dir: str | None = None
    reference_proof: str | None = None


def parse_instance(raw: Any) -> LeanProofInstance:
    instance_id, data = validate_instance_envelope(raw, task_id=TASK_ID, schema_version=SCHEMA_VERSION)

    theorem_name = require_text(data.get("theorem_name"), "data.theorem_name")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_'.]*", theorem_name):
        raise ValueError(f"Invalid Lean theorem identifier: {theorem_name!r}")
    statement = require_text(data.get("statement"), "data.statement")

    raw_imports = data.get("imports", ())
    if not isinstance(raw_imports, Sequence) or isinstance(raw_imports, (str, bytes)):
        raise ValueError("data.imports must be a list of Lean module names")
    imports: list[str] = []
    for idx, mod in enumerate(raw_imports):
        mod_str = require_text(mod, f"data.imports[{idx}]")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_'.]*", mod_str):
            raise ValueError(f"Invalid Lean import module name: {mod_str!r}")
        imports.append(mod_str)

    preamble = data.get("preamble", "")
    if not isinstance(preamble, str):
        raise ValueError("data.preamble must be a string")

    raw_axioms = data.get("allowed_axioms", sorted(ALLOWED_LEAN_AXIOMS))
    if not isinstance(raw_axioms, Sequence) or isinstance(raw_axioms, (str, bytes)):
        raise ValueError("data.allowed_axioms must be a list of axiom names")
    allowed_axioms: list[str] = []
    for ax in raw_axioms:
        ax_str = require_text(ax, "allowed_axioms entry")
        if ax_str == "sorryAx" or ax_str not in ALLOWED_LEAN_AXIOMS:
            raise ValueError(f"Disallowed axiom in instance policy: {ax_str!r}")
        allowed_axioms.append(ax_str)

    allow_sorry_seed = data.get("allow_sorry_seed", True)
    if type(allow_sorry_seed) is not bool:
        raise ValueError("data.allow_sorry_seed must be boolean")

    project_dir = data.get("project_dir")
    if project_dir is not None:
        project_dir = require_text(project_dir, "data.project_dir")

    reference_proof = data.get("reference_proof")
    if reference_proof is not None and not isinstance(reference_proof, str):
        raise ValueError("data.reference_proof must be a string when supplied")

    return LeanProofInstance(
        instance_id=instance_id,
        theorem_name=theorem_name,
        imports=tuple(imports),
        preamble=preamble,
        statement=statement,
        allowed_axioms=tuple(allowed_axioms),
        allow_sorry_seed=allow_sorry_seed,
        project_dir=project_dir,
        reference_proof=reference_proof,
    )


def generate_example(*, seed: int, size: int) -> dict[str, Any]:
    """Generate a reproducible elementary arithmetic identity proof instance."""
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(size) is not int or size < 0 or size > 1000:
        raise ValueError("size must be an integer in [0, 1000]")
    k = abs(seed) % 17 + size
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": f"lean-nat-assoc-k{k}-seed{seed}",
        "data": {
            "theorem_name": "target_theorem",
            "imports": [],
            "preamble": "",
            "statement": f"(n m : Nat) : (n + m) + {k} = n + ({k} + m)",
            "allowed_axioms": sorted(ALLOWED_LEAN_AXIOMS),
            "allow_sorry_seed": True,
            "reference_proof": "omega",
        },
    }
