"""Discovery adapter for Lean 4 theorem proving (statement-locked kernel verification)."""
from dataclasses import asdict
from typing import Any

from pathweaver.core.contracts import EvidenceLevel, IsolationError
from pathweaver.research.formal_verifier import audit_formal_source
from pathweaver.research.premise_retrieval import search_premises

from .evaluator import (
    LeanBackendUnavailableError,
    MAX_PROOF_BYTES,
    MAX_SORRY_BOUND,
    evaluate,
    evaluate_lean_source,
)
from .model import SCHEMA_VERSION, TASK_ID, parse_instance


class LeanProofDiscoveryTask:
    task_id = TASK_ID
    candidate_language = "lean"
    candidate_extension = ".lean"

    def prepare(self, raw: Any) -> dict[str, Any]:
        instance = parse_instance(raw)
        # Strip reference_proof so discovery candidates never observe solution hints.
        data: dict[str, Any] = {
            "theorem_name": instance.theorem_name,
            "imports": list(instance.imports),
            "preamble": instance.preamble,
            "statement": instance.statement,
            "allowed_axioms": list(instance.allowed_axioms),
            "allow_sorry_seed": instance.allow_sorry_seed,
        }
        if instance.project_dir is not None:
            data["project_dir"] = instance.project_dir
        if instance.imports or instance.project_dir is not None:
            try:
                premises = search_premises(
                    instance.statement,
                    imports=instance.imports,
                    project_dir=instance.project_dir,
                    top_k=4,
                )
            except Exception:
                premises = []
            if premises:
                data["available_premises"] = [
                    {
                        "name": item["name"],
                        "module": item["module"],
                        "signature": item["signature"],
                    }
                    for item in premises
                ]
        return {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": instance.instance_id,
            "data": data,
        }

    def objective_domain(self, raw: Any) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        parse_instance(raw)
        return (1, MAX_SORRY_BOUND, MAX_PROOF_BYTES), (1, 1, 1)

    def paradigm_catalog(self) -> tuple[dict[str, str], ...]:
        return (
            {
                "id": "induction_case_analysis",
                "regime": "induction_case_analysis",
                "title": "Structural Induction & Case Splitting",
                "mechanism": "Use `induction ... with | zero => ... | succ k ih => ...` or `rcases` / `by_cases` instead of blind automation.",
                "anti_pattern": "Do not repeat failing single-line `simp`/`omega` invocations.",
            },
            {
                "id": "algebraic_rewriting_automation",
                "regime": "algebraic_rewriting_automation",
                "title": "Calc-Chain & Targeted Equational Rewriting",
                "mechanism": "Introduce an explicit `calc` chain or targeted `rw [...]` lemmas rather than generic tactics.",
                "anti_pattern": "Do not guess opaque helper names not in scope.",
            },
            {
                "id": "structured_lemma_decomposition",
                "regime": "structured_lemma_decomposition",
                "title": "Intermediate `have` Subgoal Decomposition",
                "mechanism": "Decompose the goal into type-checked intermediate `have` steps (`have h_k : ... := by ...`); closing proved `have` steps strictly lowers `remaining_burden` even before all `sorry` leaves are closed.",
                "anti_pattern": "Do not spam raw unproved `sorry` placeholders without proved intermediate `have` steps, and never emit `admit`.",
            },
        )

    def validate_candidate_source(self, source: str) -> None:
        errors = audit_formal_source(source, backend="lean4", allow_sorry=True)
        if errors:
            raise ValueError("; ".join(errors))

    def evaluate_source(
        self,
        instance: dict[str, Any],
        source: str,
        *,
        wall_seconds: float = 60.0,
        seed: int = 0,
        docker_image: str | None = None,
        sandbox_mode: str = "local",
    ):
        del seed
        if sandbox_mode == "docker" and not docker_image:
            raise IsolationError(
                "LeanProofDiscoveryTask requires sandbox.lean_docker_image or sandbox.image when sandbox.mode='docker'"
            )
        allow_sorry = bool(instance["data"].get("allow_sorry_seed", True))
        try:
            result = evaluate_lean_source(
                instance,
                source,
                allow_sorry_search=allow_sorry,
                wall_seconds=wall_seconds,
                docker_image=docker_image,
                use_warm_server=(docker_image is None),
                raise_on_unavailable=True,
            )
        except LeanBackendUnavailableError as error:
            raise IsolationError(str(error)) from error
        final_source = str(result.diagnostics.get("repaired_source", source))
        solution = {
            "schema_version": SCHEMA_VERSION,
            "task_id": TASK_ID,
            "instance_id": instance["instance_id"],
            "solution": {"proof_source": final_source},
        }
        return solution, result

    def verify(self, instance: dict[str, Any], solution: dict[str, Any]):
        return evaluate(instance, solution)

    def feedback(self, result) -> dict[str, Any]:
        diag = result.diagnostics
        messages = [
            {
                "severity": msg.get("severity"),
                "line": msg.get("line"),
                "column": msg.get("column"),
                "message": str(msg.get("message", ""))[:320],
            }
            for msg in (diag.get("lean_messages") or [])[:4]
        ]
        payload: dict[str, Any] = {
            "feasible": result.feasible,
            "formal_verified": bool(diag.get("formal_verified")),
            "evidence": result.evidence.value if hasattr(result.evidence, "value") else str(result.evidence),
            "objectives": list(result.objectives) if result.objectives is not None else None,
            "sorry_count": diag.get("sorry_count"),
            "error_count": diag.get("error_count"),
            "axioms": diag.get("axioms", []),
            "violations": list(result.violations)[:4],
            "lean_messages": messages,
        }
        if "verified_steps" in diag:
            payload["verified_steps"] = diag["verified_steps"]
        if "remaining_burden" in diag:
            payload["remaining_burden"] = diag["remaining_burden"]
        if diag.get("repaired"):
            payload["repaired"] = True
        return payload

    def certificate(self, instance: dict[str, Any], solution: dict[str, Any], result):
        if not result.feasible or result.evidence != EvidenceLevel.FORMAL_VERIFIED:
            return None
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": "lean4_formal_proof",
            "instance_id": instance["instance_id"],
            "theorem_name": instance["data"]["theorem_name"],
            "solution": solution,
            "verification": asdict(result),
        }

    def brief(self) -> str:
        return """Write Lean 4 proof code (inside a ```lean code block or SEARCH/REPLACE diff) to formally prove the target theorem.
Rules:
1. Define `theorem target_theorem ...` (or the instance's named theorem) matching the locked specification, OR provide helper lemmas followed by `theorem target_theorem ...`.
2. Forbidden constructs (rejected immediately): `admit`, `axiom`, `opaque`, `unsafe`, `@[implemented_by]`, `@[extern]`, `native_decide`, `#eval`, `#exec`, `initialize`, `syntax`, `macro`, `elab`, `elab_rules`, `macro_rules`, `notation`, `infix`/`prefix`/`postfix`, `run_cmd`, `by_elab`, `Lean.Environment`/`MetavarContext`/`Expr`, `compile_inductive`, `IO.`, `System.`, `dbg_trace`, `import`, `set_option`.
3. Only standard Lean kernel axioms (`propext`, `Classical.choice`, `Quot.sound`) are permitted.
4. Verification locks the exact theorem type outside your namespace and checks `#print axioms` on the host.
5. Minimize `(incomplete_flag, remaining_burden, proof_bytes)`. Complete `sorry`-free proofs achieve `incomplete_flag = 0` (`formal_verified`). During search (`allow_sorry_seed=True`), decomposing a theorem into type-checked `have h_k : ... := by ...` steps strictly lowers `remaining_burden` even before all `sorry` leaves are closed, whereas raw unproved `sorry` spamming increases penalty.
6. Feedback reports exact Lean line/column errors and `unsolved goals` tactic states.
"""
