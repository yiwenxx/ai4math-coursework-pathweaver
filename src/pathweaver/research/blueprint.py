"""Bidirectional Lean 4 blueprint compiler and dual-prong conjecture dispatcher."""
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import re
from typing import Any

from pathweaver.core.contracts import write_json
from pathweaver.research.claims import Claim, ClaimLedger
from pathweaver.research.formal_verifier import (
    ALLOWED_LEAN_AXIOMS,
    _statement_to_prop_type,
    _strip_lean_comments_and_strings,
    audit_formal_source,
    extract_lean_theorem_names,
)
from pathweaver.tasks.lean_proof.model import SCHEMA_VERSION as LEAN_SCHEMA_VERSION, TASK_ID as LEAN_TASK_ID, parse_instance

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_'.]*$")
_PRINT_AXIOMS_RE = re.compile(r"(?m)^\s*#print\s+axioms\s+([A-Za-z0-9_.']+)")
_THEOREM_DECL_RE = re.compile(
    r"^\s*(?:(?:private|protected)\s+)?(?:theorem|lemma)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_'.]*)\s*(?P<sig>.+?)(?:\s*:=\s*(?:by\b.*|.*))?$",
    re.DOTALL,
)
_LEAN_FENCE_RE = re.compile(r"```lean4?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _module_name_for_path(root: Path, lean_file: Path) -> str:
    rel = lean_file.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] != "PathWeaverFormal" and root.name == "PathWeaverFormal":
        parts = ["PathWeaverFormal", *parts]
    return ".".join(parts)


def scan_lean_declarations(formal_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Scan ``*.lean`` modules under ``formal_dir`` for declarations, ``#print axioms``, and ``sorry`` absence."""
    root = Path(formal_dir).resolve()
    if not root.is_dir():
        return {}
    modules: dict[str, dict[str, Any]] = {}
    for lean_path in sorted(root.rglob("*.lean")):
        rel = lean_path.relative_to(root)
        if ".lake" in rel.parts:
            continue
        module_name = _module_name_for_path(root, lean_path)
        text = lean_path.read_bytes().decode("utf-8-sig")
        theorems = extract_lean_theorem_names(text)
        cleaned = _strip_lean_comments_and_strings(text)
        print_targets = _PRINT_AXIOMS_RE.findall(cleaned)
        all_errors = audit_formal_source(text, backend="lean4", allow_sorry=False)
        non_sorry_errors = set(audit_formal_source(text, backend="lean4", allow_sorry=True))
        has_sorry = any(err not in non_sorry_errors for err in all_errors)
        axioms_checked = [
            thm for thm in theorems
            if any(thm == tgt or thm.endswith(f".{tgt}") for tgt in print_targets)
        ]
        modules[module_name] = {
            "module": module_name,
            "path": rel.as_posix(),
            "theorems": theorems,
            "theorem_count": len(theorems),
            "print_axioms_targets": print_targets,
            "has_print_axioms": bool(print_targets),
            "axioms_checked_theorems": axioms_checked,
            "has_sorry": has_sorry,
            "sorry_free": not has_sorry,
            "soundness_errors": all_errors,
            "clean": not all_errors,
        }
    return modules


def _match_source_modules(source: str, modules: Mapping[str, dict[str, Any]]) -> list[str]:
    norm_source = Path(source).as_posix().lstrip("./")
    exact: list[str] = []
    for mod_name, info in modules.items():
        mod_path = str(info["path"]).lstrip("./")
        if norm_source == mod_path or norm_source.endswith(f"/{mod_path}"):
            exact.append(mod_name)
    if exact:
        return exact
    source_name = Path(norm_source).name
    by_filename = [mod_name for mod_name, info in modules.items() if Path(str(info["path"])).name == source_name]
    return by_filename if len(by_filename) == 1 else []


def _resolve_target_in_modules(
    raw_target: str | None,
    modules: Mapping[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    if not raw_target:
        return [], []
    if ":" in raw_target:
        mod_hint, thm_hint = (part.strip() for part in raw_target.split(":", 1))
    else:
        mod_hint, thm_hint = "", raw_target.strip()
    if not thm_hint:
        return [], []

    matched_mods: list[str] = []
    matched_decls: list[str] = []
    for mod_name, info in modules.items():
        if mod_hint and mod_name != mod_hint and not mod_name.endswith(f".{mod_hint}"):
            continue
        for thm in info.get("theorems") or ():
            if thm == thm_hint or thm.endswith(f".{thm_hint}"):
                matched_mods.append(mod_name)
                matched_decls.append(thm)
    return list(dict.fromkeys(matched_mods)), list(dict.fromkeys(matched_decls))


def _blueprint_state(disposition: str) -> str:
    if disposition == "formally_verified":
        return "formalized"
    if disposition == "refuted":
        return "refuted"
    if disposition == "blocked":
        return "blocked_by_dependencies"
    if disposition == "open":
        return "open_conjecture"
    return "ready_to_formalize"


class BlueprintCompiler:
    """Compile a ClaimLedger and optional Lean formal tree into a bidirectional blueprint."""

    def __init__(self, ledger: ClaimLedger, formal_dir: str | Path | None = None):
        self.ledger = ledger
        self.formal_dir = Path(formal_dir) if formal_dir is not None else None
        self.modules = scan_lean_declarations(self.formal_dir) if self.formal_dir is not None else {}

    def compile(self) -> dict[str, Any]:
        dispositions = self.ledger.dispositions()
        impact = self.ledger.impact_scores()
        formal_ev_by_claim: dict[str, list[Any]] = {}
        for item in self.ledger.evidence.values():
            if item.kind == "formal_proof":
                formal_ev_by_claim.setdefault(item.claim_id, []).append(item)

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        state_counts: dict[str, int] = {
            "formalized": 0,
            "refuted": 0,
            "ready_to_formalize": 0,
            "blocked_by_dependencies": 0,
            "open_conjecture": 0,
        }
        linked_claims = 0

        ordered_ids = sorted(self.ledger.claims.keys(), key=lambda cid: (-impact[cid], cid))
        for cid in ordered_ids:
            claim = self.ledger.claims[cid]
            disp = dispositions[cid]
            bp_state = _blueprint_state(disp)
            state_counts[bp_state] += 1

            linked_mods: list[str] = []
            linked_decls: list[str] = []
            proof_sources: list[str] = []

            if claim.formal_target:
                t_mods, t_decls = _resolve_target_in_modules(claim.formal_target, self.modules)
                linked_mods.extend(t_mods)
                linked_decls.extend(t_decls)

            for ev in formal_ev_by_claim.get(cid, ()):
                proof_sources.append(ev.source)
                s_mods = _match_source_modules(ev.source, self.modules)
                linked_mods.extend(s_mods)
                if ev.theorem_name:
                    e_mods, e_decls = _resolve_target_in_modules(ev.theorem_name, self.modules)
                    linked_mods.extend(e_mods)
                    linked_decls.extend(e_decls)
                else:
                    for mod_name in s_mods:
                        linked_decls.extend(self.modules[mod_name].get("axioms_checked_theorems") or ())

            linked_mods = list(dict.fromkeys(linked_mods))
            linked_decls = list(dict.fromkeys(linked_decls))
            if linked_mods or linked_decls:
                linked_claims += 1
            verified_in_scan = bool(linked_mods) and all(
                bool(self.modules[m]["clean"]) for m in linked_mods
            )
            if claim.formal_target and not linked_decls:
                verified_in_scan = False

            blocking_deps = [
                dep for dep in claim.dependencies if dispositions[dep] not in {"reviewed", "formally_verified"}
            ]
            nodes.append({
                "claim_id": cid,
                "blueprint_state": bp_state,
                "disposition": disp,
                "impact_score": impact[cid],
                "dependencies": list(claim.dependencies),
                "blocking_dependencies": blocking_deps,
                "related": list(claim.related),
                "formal_target": claim.formal_target,
                "statement": claim.statement,
                "scope": claim.scope,
                "formal_proof_sources": proof_sources,
                "linked_modules": linked_mods,
                "linked_declarations": linked_decls,
                "declaration_verified_in_scan": verified_in_scan,
            })
            for dep in claim.dependencies:
                edges.append({"from": dep, "to": cid, "kind": "dependency"})

        return {
            "schema_version": 1,
            "summary": {
                "claim_count": len(self.ledger.claims),
                "evidence_count": len(self.ledger.evidence),
                "state_counts": state_counts,
                "formal_modules_scanned": len(self.modules),
                "linked_claims": linked_claims,
                "ready_queue": [n["claim_id"] for n in nodes if n["blueprint_state"] == "ready_to_formalize"],
            },
            "nodes": nodes,
            "edges": edges,
            "modules": self.modules,
        }

    def to_mermaid(self) -> str:
        """Render the compiled claim dependency graph as a Mermaid ``flowchart TD`` diagram."""
        compiled = self.compile()
        lines = [
            "flowchart TD",
            "  classDef formalized fill:#d4edda,stroke:#28a745,color:#155724;",
            "  classDef refuted fill:#f8d7da,stroke:#dc3545,color:#721c24;",
            "  classDef ready_to_formalize fill:#cce5ff,stroke:#004085,color:#004085;",
            "  classDef blocked_by_dependencies fill:#fff3cd,stroke:#856404,color:#856404;",
            "  classDef open_conjecture fill:#e2e3e5,stroke:#6c757d,color:#383d41;",
        ]
        id_map: dict[str, str] = {}
        used_ids: set[str] = set()
        for node in compiled["nodes"]:
            cid = str(node["claim_id"])
            base = re.sub(r"[^A-Za-z0-9_]", "_", cid)
            if not base or not (base[0].isalpha() or base[0] == "_"):
                base = f"c_{base}"
            candidate = base
            idx = 2
            while candidate in used_ids:
                candidate = f"{base}_{idx}"
                idx += 1
            used_ids.add(candidate)
            id_map[cid] = candidate

            state = str(node["blueprint_state"])
            target_suffix = f" | {node['formal_target']}" if node["formal_target"] else ""
            raw_label = f"{cid} [{state}]{target_suffix}"
            safe_label = raw_label.replace('"', "'").replace("[", "(").replace("]", ")")
            lines.append(f'  {candidate}["{safe_label}"]:::{state}')

        for edge in compiled["edges"]:
            src = id_map.get(edge["from"])
            dst = id_map.get(edge["to"])
            if src and dst:
                lines.append(f"  {src} --> {dst}")
        return "\n".join(lines) + "\n"


def _parse_lean_statement(text: str) -> tuple[str | None, str] | None:
    """Extract ``(optional_theorem_name, lean_statement)`` when ``text`` contains a Lean declaration/Prop."""
    stripped = text.strip()
    fence = _LEAN_FENCE_RE.search(stripped)
    candidate = fence.group(1).strip() if fence else stripped
    m_decl = _THEOREM_DECL_RE.match(candidate)
    if m_decl:
        thm_name = m_decl.group("name").rsplit(".", 1)[-1]
        sig = m_decl.group("sig").strip()
        try:
            _statement_to_prop_type(sig)
            return thm_name, sig
        except ValueError:
            return None

    looks_lean = (
        candidate.startswith((":", "∀", "∃", "forall "))
        or (candidate.startswith(("(", "{", "[")) and ":" in candidate)
    )
    if not looks_lean:
        return None
    normalized = f": {candidate}" if candidate.startswith(("∀", "∃", "forall ")) else candidate
    try:
        _statement_to_prop_type(normalized)
        return None, normalized
    except ValueError:
        return None


def _safe_lean_theorem_name(raw_name: str, fallback_claim_id: str) -> str:
    leaf = raw_name.strip().rsplit(".", 1)[-1] if raw_name.strip() else ""
    if leaf and _IDENT_RE.fullmatch(leaf):
        return leaf
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", fallback_claim_id).strip("_")
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"claim_{sanitized}" if sanitized else "target_theorem"
    return sanitized


def probe_and_dispatch_conjectures(
    bundle: Mapping[str, Any],
    *,
    bundle_root: Path,
    output_dir: Path | None = None,
    probe_callbacks: Sequence[Callable[[Claim], dict[str, Any] | None]] = (),
) -> dict[str, Any]:
    """Run fast counterexample probes (left prong) and emit standalone ``lean_proof`` tasks (right prong)."""
    root = Path(bundle_root).resolve()
    updated_bundle: dict[str, Any] = {
        "schema_version": bundle["schema_version"],
        "claims": list(bundle["claims"]),
        "evidence": list(bundle["evidence"]),
    }
    ledger = ClaimLedger()
    ledger.apply(updated_bundle, root)

    dispositions = ledger.dispositions()
    impact = ledger.impact_scores()
    used_ev_ids = set(ledger.evidence.keys())
    probed_count = 0
    refuted_claims: list[str] = []

    probe_candidates = sorted(
        (cid for cid, st in dispositions.items() if st in {"open", "candidate"}),
        key=lambda cid: (-impact[cid], cid),
    )
    for cid in probe_candidates:
        claim = ledger.claims[cid]
        if not probe_callbacks:
            continue
        probed_count += 1
        for callback in probe_callbacks:
            outcome = callback(claim)
            if not isinstance(outcome, Mapping):
                continue
            raw_rel = str(outcome.get("evidence_file") or f"probes/{cid}-counterexample.txt")
            rel_path = Path(raw_rel)
            target_path = (root / rel_path).resolve()
            if rel_path.anchor or not target_path.is_relative_to(root):
                raise ValueError(f"Counterexample evidence must reside inside bundle_root: {raw_rel!r}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            content = outcome.get("content", "")
            if isinstance(content, bytes):
                target_path.write_bytes(content)
            else:
                target_path.write_text(str(content), encoding="utf-8", newline="\n")

            ev_id = f"{cid}-counterexample"
            suffix = 2
            while ev_id in used_ev_ids:
                ev_id = f"{cid}-counterexample-{suffix}"
                suffix += 1
            used_ev_ids.add(ev_id)

            updated_bundle["evidence"].append({
                "id": ev_id,
                "claim_id": cid,
                "kind": "counterexample",
                "summary": str(outcome.get("summary") or f"Counterexample probe refuted {cid}"),
                "source": rel_path.as_posix(),
            })
            refuted_claims.append(cid)
            break

    if refuted_claims:
        ledger = ClaimLedger()
        ledger.apply(updated_bundle, root)
        dispositions = ledger.dispositions()
        impact = ledger.impact_scores()

    compiled = BlueprintCompiler(ledger).compile()
    dispatched_instances: list[dict[str, Any]] = []
    emitted_files: list[str] = []
    if output_dir is not None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    for node in compiled["nodes"]:
        cid = str(node["claim_id"])
        bp_state = str(node["blueprint_state"])
        disp = str(node["disposition"])
        if bp_state in {"refuted", "formalized"}:
            continue
        if bp_state != "ready_to_formalize" and disp != "candidate":
            continue
        claim = ledger.claims[cid]
        parsed_stmt = _parse_lean_statement(claim.statement)
        if not claim.formal_target and parsed_stmt is None:
            continue

        imports: list[str] = []
        raw_thm = ""
        if claim.formal_target:
            if ":" in claim.formal_target:
                mod_part, thm_part = claim.formal_target.split(":", 1)
                if mod_part.strip():
                    imports.append(mod_part.strip())
                raw_thm = thm_part.strip()
            else:
                raw_thm = claim.formal_target.strip()
        if not raw_thm and parsed_stmt is not None and parsed_stmt[0]:
            raw_thm = parsed_stmt[0]
        theorem_name = _safe_lean_theorem_name(raw_thm, cid)
        lean_stmt = parsed_stmt[1] if parsed_stmt is not None else f": {claim.statement}"

        task_instance: dict[str, Any] = {
            "schema_version": LEAN_SCHEMA_VERSION,
            "task_id": LEAN_TASK_ID,
            "instance_id": f"claim-{cid}",
            "data": {
                "theorem_name": theorem_name,
                "imports": imports,
                "preamble": "",
                "statement": lean_stmt,
                "allowed_axioms": sorted(ALLOWED_LEAN_AXIOMS),
                "allow_sorry_seed": True,
            },
        }
        parse_instance(task_instance)
        dispatched_instances.append(task_instance)
        if output_dir is not None:
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", cid) + ".json"
            out_path = Path(output_dir) / safe_name
            write_json(task_instance, out_path)
            emitted_files.append(str(out_path))

    return {
        "probed_count": probed_count,
        "refuted_count": len(refuted_claims),
        "refuted_claims": refuted_claims,
        "dispatched_count": len(dispatched_instances),
        "dispatched_claims": [inst["instance_id"].removeprefix("claim-") for inst in dispatched_instances],
        "emitted_files": emitted_files,
        "instances": dispatched_instances,
        "dispositions": dispositions,
        "bundle": updated_bundle,
    }
