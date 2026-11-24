"""Apollo-style Lean 4 proof repair (hole filling + failing tactic repair) and subgoal extraction."""
from collections.abc import Mapping, Sequence
import re
import time
from typing import Any

from pathweaver.research.formal_verifier import (
    FormalVerificationResult,
    _strip_lean_comments_and_strings,
    build_locked_lean_module,
    verify_formal_proof,
)
from pathweaver.tasks.lean_proof.model import (
    LeanProofInstance,
    SCHEMA_VERSION,
    TASK_ID,
    parse_instance,
)

_HOLE_FILL_TACTICS = ("rfl", "decide", "omega", "simp", "assumption", "contradiction")
_LINE_REPAIR_TACTICS = ("omega", "decide", "simp", "rfl", "aesop", "linarith")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")


def _split_statement_binders_and_body(statement: str) -> tuple[str, str]:
    """Split `(x : T) ... : Body` into `(binders, body)` at top-level `:`."""
    text = statement.strip()
    if text.startswith(":"):
        return "", text[1:].strip()
    depth = 0
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return text[:i].strip(), text[i + 1 :].strip()
        i += 1
    return "", text


def _split_binder_groups(binders: str) -> list[tuple[set[str], str]]:
    """Split `(a b : Nat) {c : Type} [Fact p]` into `({names}, chunk_text)` items."""
    groups: list[tuple[set[str], str]] = []
    i = 0
    n = len(binders)
    while i < n:
        while i < n and binders[i].isspace():
            i += 1
        if i >= n:
            break
        open_ch = binders[i]
        if open_ch not in "({[":
            break
        close_ch = { "(": ")", "{": "}", "[": "]" }[open_ch]
        depth = 0
        in_str = False
        start = i
        while i < n:
            ch = binders[i]
            if in_str:
                if ch == "\\" and i + 1 < n:
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        chunk = binders[start:i]
        inner = chunk[1:-1]
        colon_pos = inner.find(":")
        names: set[str] = set()
        if colon_pos != -1:
            lhs = inner[:colon_pos]
            names = set(_IDENT_RE.findall(lhs))
        groups.append((names, chunk))
    return groups


def _select_relevant_outer_binders(outer_binders: str, inner_binders: str, body: str) -> str:
    """Keep outer binder groups referenced in `body` (transitively across binder types) and unshadowed."""
    groups = _split_binder_groups(outer_binders)
    if not groups:
        return ""
    shadowed: set[str] = set()
    for names, _ in _split_binder_groups(inner_binders):
        shadowed |= names

    referenced: set[str] = set(_IDENT_RE.findall(body)) | set(_IDENT_RE.findall(inner_binders))
    selected = [False] * len(groups)
    changed = True
    while changed:
        changed = False
        for idx in range(len(groups) - 1, -1, -1):
            if selected[idx]:
                continue
            names, chunk = groups[idx]
            unshadowed = names - shadowed
            if unshadowed & referenced or (not names and chunk.startswith("[") and bool(set(_IDENT_RE.findall(chunk)) & referenced)):
                selected[idx] = True
                referenced |= set(_IDENT_RE.findall(chunk))
                changed = True
    return " ".join(chunk for keep, (_, chunk) in zip(selected, groups) if keep)


def _safe_lean_ident(raw: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_'.]", "_", raw.strip())
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned[0]):
        cleaned = f"{fallback}_{cleaned}" if cleaned else fallback
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_'.]*", cleaned):
        return fallback
    return cleaned


def _make_subgoal_instance(
    inst: LeanProofInstance,
    *,
    index: int,
    raw_name: str,
    statement: str,
    kind: str,
    line: int | None,
) -> dict[str, Any]:
    safe_thm = _safe_lean_ident(raw_name, f"subgoal_{index}")
    safe_id_suffix = re.sub(r"[^A-Za-z0-9_-]", "_", safe_thm)
    data: dict[str, Any] = {
        "theorem_name": safe_thm,
        "imports": list(inst.imports),
        "preamble": inst.preamble,
        "statement": statement,
        "allowed_axioms": list(inst.allowed_axioms),
        "allow_sorry_seed": inst.allow_sorry_seed,
    }
    if inst.project_dir is not None:
        data["project_dir"] = inst.project_dir
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "instance_id": f"{inst.instance_id}__subgoal_{index}_{safe_id_suffix}",
        "data": data,
        "metadata": {
            "parent_instance_id": inst.instance_id,
            "subgoal_kind": kind,
            "line": line,
        },
    }


def _scan_have_sorry_subgoals(inst: LeanProofInstance, source: str) -> list[dict[str, Any]]:
    cleaned = _strip_lean_comments_and_strings(source).replace("\r\n", "\n")
    orig_lines = source.replace("\r\n", "\n").split("\n")
    clean_lines = cleaned.split("\n")
    outer_binders, _ = _split_statement_binders_and_body(inst.statement)

    extracted: list[dict[str, Any]] = []
    seen_statements: set[str] = set()
    have_re = re.compile(r"(?m)^([ \t]*)have\b")

    for idx_match, match in enumerate(have_re.finditer(cleaned)):
        indent = len(match.group(1))
        pos = match.end()
        n = len(cleaned)
        while pos < n and cleaned[pos].isspace():
            pos += 1

        # Optional `have` name before binders or `:`
        have_name = ""
        if pos < n and (cleaned[pos].isalpha() or cleaned[pos] == "_"):
            name_m = _IDENT_RE.match(cleaned, pos)
            if name_m:
                have_name = name_m.group(0)
                pos = name_m.end()

        # Scan top-level binders until `:` (not `:=`)
        depth = 0
        colon_pos: int | None = None
        binder_start = pos
        while pos < n:
            ch = cleaned[pos]
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth = max(0, depth - 1)
            elif ch == ":" and depth == 0 and cleaned[pos : pos + 2] != ":=":
                colon_pos = pos
                break
            elif cleaned[pos : pos + 2] == ":=" and depth == 0:
                break
            pos += 1
        if colon_pos is None:
            continue

        inner_binders = source[binder_start:colon_pos].strip()
        # Scan type up to top-level `:=`
        pos = colon_pos + 1
        depth = 0
        assign_pos: int | None = None
        while pos < n:
            ch = cleaned[pos]
            if ch in "({[":
                depth += 1
            elif ch in ")}]":
                depth = max(0, depth - 1)
            elif cleaned[pos : pos + 2] == ":=" and depth == 0:
                assign_pos = pos
                break
            pos += 1
        if assign_pos is None:
            continue

        have_type = " ".join(source[colon_pos + 1 : assign_pos].split())
        if not have_type:
            continue

        # Determine indented body slice belonging to this `have`
        start_line = cleaned[: match.start()].count("\n")
        body_end_pos = n
        for line_i in range(start_line + 1, len(clean_lines)):
            line_text = clean_lines[line_i]
            if not line_text.strip():
                continue
            line_indent = len(line_text) - len(line_text.lstrip(" \t"))
            if line_indent <= indent:
                body_end_pos = sum(len(l) + 1 for l in clean_lines[:line_i])
                break

        body_slice = cleaned[assign_pos:body_end_pos]
        if not re.search(r"\bsorry\b", body_slice):
            continue

        outer_kept = _select_relevant_outer_binders(outer_binders, inner_binders, have_type)
        all_binders = " ".join(part for part in (outer_kept, inner_binders) if part)
        stmt = f"{all_binders} : {have_type}" if all_binders else f": {have_type}"
        if stmt in seen_statements:
            continue
        seen_statements.add(stmt)
        extracted.append(
            _make_subgoal_instance(
                inst,
                index=len(extracted) + 1,
                raw_name=have_name or f"have_subgoal_{idx_match + 1}",
                statement=stmt,
                kind="have_sorry",
                line=start_line + 1 if start_line < len(orig_lines) else None,
            )
        )
    return extracted


def _parse_unsolved_goal_diagnostic(message: str) -> list[str]:
    """Extract standalone Lean statements `(hyps...) : goal` from an `unsolved goals` diagnostic."""
    if "unsolved goals" not in message and "⊢" not in message:
        return []
    blocks = re.split(r"(?m)^\s*case\s+.*$", message)
    statements: list[str] = []
    for block in blocks:
        if "⊢" not in block:
            continue
        ctx_text, goal_text = block.split("⊢", 1)
        goal = " ".join(
            line.strip()
            for line in goal_text.strip().splitlines()
            if line.strip() and not line.strip().startswith("unsolved goals")
        )
        if not goal:
            continue
        binders: list[str] = []
        skip_goal = False
        for raw_line in ctx_text.splitlines():
            line = raw_line.strip()
            if not line or line == "unsolved goals" or ":" not in line:
                continue
            lhs, rhs = line.split(":", 1)
            lhs = lhs.strip()
            rhs = rhs.strip()
            if not lhs or not rhs:
                continue
            if "✝" in lhs or "✝" in rhs:
                # Skip inaccessible auto-generated names; if referenced in goal, skip this goal safely.
                for tok in lhs.split():
                    if "✝" in tok and tok in goal:
                        skip_goal = True
                continue
            binders.append(f"({lhs} : {rhs})")
        if skip_goal or "✝" in goal:
            continue
        stmt = f"{' '.join(binders)} : {goal}" if binders else f": {goal}"
        statements.append(stmt)
    return statements


def extract_sorry_subgoals(
    instance: LeanProofInstance | Mapping[str, Any],
    candidate_source: str,
    diagnostics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Package `have ... sorry` blocks and `unsolved goals` diagnostics as standalone `lean_proof` instances."""
    inst = instance if isinstance(instance, LeanProofInstance) else parse_instance(instance)
    subgoals = _scan_have_sorry_subgoals(inst, candidate_source)
    seen_stmts = {item["data"]["statement"] for item in subgoals}

    for diag in diagnostics:
        msg = str(diag.get("message", ""))
        line_no = diag.get("line") if isinstance(diag.get("line"), int) else None
        for stmt in _parse_unsolved_goal_diagnostic(msg):
            if stmt in seen_stmts:
                continue
            seen_stmts.add(stmt)
            subgoals.append(
                _make_subgoal_instance(
                    inst,
                    index=len(subgoals) + 1,
                    raw_name=f"unsolved_goal_{len(subgoals) + 1}",
                    statement=stmt,
                    kind="unsolved_goal",
                    line=line_no,
                )
            )
    return subgoals


def _wrapped_candidate_offset(inst: LeanProofInstance, source: str, wrapped: str) -> int:
    """Return 1-based line number where `source` begins inside `wrapped`."""
    wrapped_lines = wrapped.splitlines()
    try:
        ns_idx = wrapped_lines.index("namespace _PathWeaverCandidate")
    except ValueError:
        return 1
    cleaned = _strip_lean_comments_and_strings(source)
    has_thm = bool(re.search(rf"\b(?:theorem|lemma)\s+{re.escape(inst.theorem_name)}\b", cleaned))
    return ns_idx + 2 if has_thm else ns_idx + 3


def _map_diagnostics_to_candidate(
    diagnostics: Sequence[Mapping[str, Any]],
    cand_start_line: int,
    cand_line_count: int,
) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for diag in diagnostics:
        item = dict(diag)
        line_val = item.get("line")
        if isinstance(line_val, int):
            rel_line = line_val - cand_start_line + 1
            if 1 <= rel_line <= cand_line_count:
                item["line"] = rel_line
        mapped.append(item)
    return mapped


def _generate_line_candidates(cand_lines: list[str], line_idx: int, message: str, tactic: str) -> list[str]:
    results: list[str] = []
    if 0 <= line_idx < len(cand_lines):
        orig = cand_lines[line_idx]
        indent = orig[: len(orig) - len(orig.lstrip(" \t"))]
        stripped = orig.strip()
        by_match = re.match(r"^(.*?:\s*=\s*by|.*?:=\s*by)\b(.*)$", orig)
        if by_match:
            prefix = by_match.group(1)
            tail = by_match.group(2).strip()
            if tail:
                trial_lines = list(cand_lines)
                trial_lines[line_idx] = f"{prefix} {tactic}"
                results.append("\n".join(trial_lines))
        if not re.match(r"^(?:theorem|lemma|def|abbrev|structure|have)\b", stripped):
            trial_lines = list(cand_lines)
            trial_lines[line_idx] = f"{indent}{tactic}"
            results.append("\n".join(trial_lines))
        if "unsolved goals" in message.lower():
            trial_lines = list(cand_lines)
            extra_indent = f"{indent}  " if by_match and not by_match.group(2).strip() else indent
            trial_lines.insert(line_idx + 1, f"{extra_indent}{tactic}")
            results.append("\n".join(trial_lines))
    elif cand_lines and "unsolved goals" in message.lower():
        last = cand_lines[-1]
        indent = last[: len(last) - len(last.lstrip(" \t"))]
        trial_lines = list(cand_lines) + [f"{indent}{tactic}"]
        results.append("\n".join(trial_lines))
    return results


def repair_lean_proof(
    instance: LeanProofInstance | Mapping[str, Any],
    candidate_source: str,
    *,
    wall_seconds: float = 15.0,
    use_warm_server: bool = True,
) -> dict[str, Any]:
    """Attempt hole-filling (`sorry` -> closing tactics) and failing tactic line repair."""
    inst = instance if isinstance(instance, LeanProofInstance) else parse_instance(instance)
    deadline = time.monotonic() + max(0.5, wall_seconds)
    allowed = frozenset(inst.allowed_axioms)

    def _check(src: str) -> tuple[FormalVerificationResult | None, int]:
        remaining = deadline - time.monotonic()
        if remaining <= 0.1:
            return None, 1
        wrapped = build_locked_lean_module(
            inst.theorem_name,
            inst.statement,
            src,
            imports=inst.imports,
            preamble=inst.preamble,
            allow_sorry=True,
        )
        offset = _wrapped_candidate_offset(inst, src, wrapped)
        verdict = verify_formal_proof(
            wrapped,
            backend="lean4",
            theorem_name="_pathweaver_verified_target",
            project_dir=inst.project_dir,
            timeout_seconds=min(remaining, 10.0),
            allowed_axioms=allowed,
            allow_partial_sorry=True,
            use_warm_server=use_warm_server,
        )
        return verdict, offset

    try:
        current_verdict, current_offset = _check(candidate_source)
    except ValueError as err:
        return {
            "repaired": False,
            "status": "rejected_soundness",
            "original_source": candidate_source,
            "repaired_source": candidate_source,
            "sorry_count": 0,
            "error_count": 1,
            "applied_repairs": [],
            "soundness_errors": [str(err)],
            "subgoals": [],
            "verdict": None,
        }

    if current_verdict is None:
        return {
            "repaired": False,
            "status": "failed",
            "original_source": candidate_source,
            "repaired_source": candidate_source,
            "sorry_count": 0,
            "error_count": 1,
            "applied_repairs": [],
            "subgoals": [],
            "verdict": None,
        }

    if current_verdict.status == "backend_unavailable":
        return {
            "repaired": False,
            "status": "backend_unavailable",
            "original_source": candidate_source,
            "repaired_source": candidate_source,
            "sorry_count": current_verdict.sorry_count,
            "error_count": current_verdict.error_count,
            "applied_repairs": [],
            "subgoals": [],
            "verdict": current_verdict,
        }

    current_source = candidate_source
    repaired = False
    applied_repairs: list[dict[str, Any]] = []

    if current_verdict.status == "verified":
        return {
            "repaired": False,
            "status": "verified",
            "original_source": candidate_source,
            "repaired_source": current_source,
            "sorry_count": 0,
            "error_count": 0,
            "applied_repairs": [],
            "subgoals": [],
            "verdict": current_verdict,
        }

    # Step B: Failing tactic line repair (up to 3 improvement passes while errors remain)
    for _ in range(3):
        if current_verdict.error_count <= 0 or time.monotonic() >= deadline:
            break
        error_diags = [d for d in current_verdict.diagnostics if d.get("severity") == "error"]
        if not error_diags:
            break
        cand_lines = current_source.splitlines()
        improved_line = False
        for err_diag in error_diags[:3]:
            if time.monotonic() >= deadline:
                break
            raw_line = err_diag.get("line")
            line_idx = (raw_line - current_offset) if isinstance(raw_line, int) else len(cand_lines) - 1
            msg = str(err_diag.get("message", ""))
            for tactic in _LINE_REPAIR_TACTICS:
                if time.monotonic() >= deadline:
                    break
                for trial in _generate_line_candidates(cand_lines, line_idx, msg, tactic):
                    if time.monotonic() >= deadline:
                        break
                    try:
                        trial_verdict, trial_offset = _check(trial)
                    except ValueError:
                        continue
                    if trial_verdict is None:
                        continue
                    is_better = (
                        trial_verdict.status == "verified"
                        or (
                            trial_verdict.status == "incomplete_sorry"
                            and trial_verdict.error_count == 0
                        )
                        or (
                            trial_verdict.status == "failed"
                            and trial_verdict.error_count < current_verdict.error_count
                        )
                    )
                    if is_better:
                        current_source = trial
                        current_verdict = trial_verdict
                        current_offset = trial_offset
                        repaired = True
                        applied_repairs.append({
                            "step": "failing_line_repair",
                            "line": line_idx + 1,
                            "tactic": tactic,
                        })
                        improved_line = True
                        break
                if improved_line:
                    break
            if improved_line:
                break
        if not improved_line or current_verdict.status == "verified":
            break

    # Step A: Hole filling (`sorry` -> closing tactics one hole at a time)
    if current_verdict.error_count == 0 and current_verdict.status != "verified":
        hole_idx = 0
        while time.monotonic() < deadline:
            cleaned = _strip_lean_comments_and_strings(current_source)
            holes = list(re.finditer(r"\bsorry\b", cleaned))
            if hole_idx >= len(holes):
                break
            match = holes[hole_idx]
            filled = False
            for tactic in _HOLE_FILL_TACTICS:
                if time.monotonic() >= deadline:
                    break
                trial = current_source[: match.start()] + tactic + current_source[match.end() :]
                try:
                    trial_verdict, trial_offset = _check(trial)
                except ValueError:
                    continue
                if trial_verdict is None:
                    continue
                if (
                    trial_verdict.error_count == 0
                    and trial_verdict.status in {"verified", "incomplete_sorry"}
                    and (
                        trial_verdict.status == "verified"
                        or trial_verdict.sorry_count < current_verdict.sorry_count
                    )
                ):
                    hole_line = current_source[: match.start()].count("\n") + 1
                    current_source = trial
                    current_verdict = trial_verdict
                    current_offset = trial_offset
                    repaired = True
                    applied_repairs.append({
                        "step": "hole_filling",
                        "line": hole_line,
                        "tactic": tactic,
                    })
                    filled = True
                    break
            if current_verdict.status == "verified":
                break
            if not filled:
                hole_idx += 1

    mapped_diags = _map_diagnostics_to_candidate(
        current_verdict.diagnostics,
        current_offset,
        len(current_source.splitlines()),
    )
    subgoals = (
        []
        if current_verdict.status == "verified"
        else extract_sorry_subgoals(inst, current_source, mapped_diags)
    )
    return {
        "repaired": repaired,
        "status": current_verdict.status,
        "original_source": candidate_source,
        "repaired_source": current_source,
        "sorry_count": current_verdict.sorry_count,
        "error_count": current_verdict.error_count,
        "applied_repairs": applied_repairs,
        "subgoals": subgoals,
        "verdict": current_verdict,
    }
