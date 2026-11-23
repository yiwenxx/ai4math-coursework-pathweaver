"""Lean 4 kernel verification bridge (Tier 2 -> Tier 5) with statement locking and axiom audit.

Supports local `lake env lean --json` / `lean --json` or an immutable read-only
networkless Docker image, with nested-comment-safe escape scanning, namespace
isolation, and `#print axioms` checking. Always fails closed if Lean is unavailable.
"""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any

from pathweaver.core.contracts import digest


ALLOWED_LEAN_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

_LEAN_FORBIDDEN_PATTERNS = (
    (re.compile(r"\bsorry\b"), "sorry"),
    (re.compile(r"\badmit\b"), "admit"),
    (re.compile(r"(?m)^\s*(?:private\s+|protected\s+)?axiom\b"), "custom axiom"),
    (re.compile(r"(?m)^\s*(?:private\s+|protected\s+)?opaque\b"), "opaque constant"),
    (re.compile(r"\bunsafe\b"), "unsafe declaration"),
    (re.compile(r"@\[[^\]]*\bimplemented_by\b"), "@[implemented_by]"),
    (re.compile(r"@\[[^\]]*\bextern\b"), "@[extern]"),
    (re.compile(r"\bLean\.ofReduceBool\b|\bLean\.trustCompiler\b"), "compiler trust bypass"),
    (re.compile(r"\bnative_decide\b"), "native_decide (disabled under strict kernel policy)"),
    (re.compile(r"(?m)^\s*#(?:eval|exec)\b"), "#eval/#exec metaprogramming execution"),
    (re.compile(r"(?m)^\s*(?:builtin_)?initialize\b"), "initialize hook"),
    (re.compile(r"(?m)^\s*(?:local\s+)?(?:elab|macro_rules)\b"), "custom elaborator/macro"),
    (re.compile(r"\b(?:IO\.|System\.|dbg_trace)\b"), "IO/System/dbg_trace access"),
)

_LEAN_FORBIDDEN_WITHOUT_SORRY = tuple(
    (regex, label) for regex, label in _LEAN_FORBIDDEN_PATTERNS if label not in {"sorry", "admit"}
)


@dataclass(frozen=True)
class FormalVerificationResult:
    status: str  # "verified" | "incomplete_sorry" | "rejected_soundness" | "failed" | "backend_unavailable"
    backend: str
    theorem_name: str | None
    source_sha256: str
    axioms: tuple[str, ...] = ()
    soundness_errors: tuple[str, ...] = ()
    compiler_output: str = ""
    evidence_kind: str = "formal_proof"
    diagnostics: tuple[dict[str, Any], ...] = ()
    error_count: int = 0
    sorry_count: int = 0
    wall_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["axioms"] = list(self.axioms)
        payload["soundness_errors"] = list(self.soundness_errors)
        payload["diagnostics"] = [dict(item) for item in self.diagnostics]
        return payload


def resolve_lean_executable(name: str = "lean") -> str | None:
    """Resolve `lean` or `lake` from PATH or `~/.elan/bin`."""
    found = shutil.which(name)
    if found:
        return str(Path(found).resolve())
    suffix = ".exe" if os.name == "nt" and not name.endswith(".exe") else ""
    candidate = Path.home() / ".elan" / "bin" / f"{name}{suffix}"
    return str(candidate.resolve()) if candidate.is_file() else None


def default_formal_project_dir() -> Path | None:
    """Return the bundled PathWeaverFormal Lake project directory when present."""
    candidate = Path(__file__).resolve().parents[3] / "formal"
    if (candidate / "lakefile.toml").is_file() or (candidate / "lakefile.lean").is_file():
        return candidate
    return None


def _run_subprocess(cmd: list[str], *, cwd: Path | None, timeout: float) -> subprocess.CompletedProcess[str]:
    opts: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if cwd is not None:
        opts["cwd"] = str(cwd)
    if os.name == "nt":
        opts["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **opts)


def lean_toolchain_status(project_dir: str | Path | None = None) -> dict[str, Any]:
    """Inspect installed Lean 4 / Lake binaries and project readiness without modifying state."""
    lean_bin = resolve_lean_executable("lean")
    lake_bin = resolve_lean_executable("lake")
    resolved_project = Path(project_dir).resolve() if project_dir is not None else default_formal_project_dir()

    def _version(exe: str | None) -> str | None:
        if not exe:
            return None
        try:
            proc = _run_subprocess([exe, "--version"], cwd=None, timeout=10)
            return proc.stdout.strip() if proc.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    return {
        "lean_available": lean_bin is not None,
        "lake_available": lake_bin is not None,
        "lean_executable": lean_bin,
        "lake_executable": lake_bin,
        "lean_version": _version(lean_bin),
        "lake_version": _version(lake_bin),
        "formal_project_dir": str(resolved_project) if resolved_project is not None else None,
        "formal_project_built": bool(
            resolved_project is not None
            and (resolved_project / ".lake" / "build" / "lib" / "lean" / "PathWeaverFormal.olean").is_file()
        ),
    }


def _strip_lean_comments_and_strings(source: str) -> str:
    """Strip Lean 4 nested `/- -/` block comments, `--` line comments, and string literals."""
    out: list[str] = []
    i, n = 0, len(source)
    block_depth = 0
    in_string = False
    while i < n:
        ch, nxt = source[i], source[i : i + 2]
        if block_depth > 0:
            if nxt == "/-":
                block_depth += 1
                out.append("  ")
                i += 2
            elif nxt == "-/":
                block_depth -= 1
                out.append("  ")
                i += 2
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif in_string:
            if ch == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
            elif ch == '"':
                in_string = False
                out.append('"')
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif nxt == "/-":
            block_depth = 1
            out.append("  ")
            i += 2
        elif nxt == "--":
            while i < n and source[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == '"':
            in_string = True
            out.append('"')
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def extract_lean_theorem_names(source: str) -> list[str]:
    """Resolve declaration names for the axiom audit appended at module scope."""
    cleaned = _strip_lean_comments_and_strings(source.lstrip("\ufeff"))
    identifier = r"[^\W\d][\w']*(?:\.[^\W\d][\w']*)*"
    commands = re.compile(
        rf"^[ \t]*(?:namespace[ \t]+(?P<namespace>{identifier})[ \t]*$"
        rf"|(?P<section>(?:noncomputable[ \t]+)?section)(?:[ \t]+{identifier})?[ \t]*$"
        rf"|(?P<end>end)(?:[ \t]+{identifier})?[ \t]*$"
        rf"|(?:(?:private|protected)\s+)?(?:theorem|lemma)\s+(?P<theorem>{identifier}))",
        re.MULTILINE,
    )
    scopes = []
    names = []
    for command in commands.finditer(cleaned.replace("\r\n", "\n")):
        if command.lastgroup == "namespace":
            scopes.append(command["namespace"])
        elif command.lastgroup == "section":
            scopes.append("")
        elif command.lastgroup == "end":
            if scopes:
                scopes.pop()
        else:
            name = command["theorem"]
            if name.startswith("_root_."):
                names.append(name.removeprefix("_root_."))
            else:
                names.append(".".join(part for part in [*scopes, name] if part))
    return names


def audit_formal_source(
    source: str,
    backend: str = "lean4",
    *,
    allow_sorry: bool = False,
) -> list[str]:
    """Scan Lean 4 proof source for soundness escapes before invoking the kernel."""
    if backend != "lean4":
        return [f"Unsupported formal backend: {backend!r} (only 'lean4' is supported)"]
    if not isinstance(source, str) or not source.strip():
        return ["Formal proof source must be nonempty text"]
    cleaned = _strip_lean_comments_and_strings(source)
    patterns = _LEAN_FORBIDDEN_WITHOUT_SORRY if allow_sorry else _LEAN_FORBIDDEN_PATTERNS
    return [f"Forbidden proof construct detected: {label}" for regex, label in patterns if regex.search(cleaned)]


def _statement_to_prop_type(locked_statement: str) -> str:
    """Convert `(x : T) ... : Body` or `: Body` into a closed Prop type after `:`."""
    text = locked_statement.strip()
    if text.startswith(":"):
        return text[1:].strip()
    depth, in_string, i = 0, False, 0
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
            binders, body = text[:i].strip(), text[i + 1 :].strip()
            return f"∀ {binders}, {body}" if binders else body
        i += 1
    raise ValueError("Locked Lean statement must contain a top-level `:` separating binders and type")


def build_locked_lean_module(
    theorem_name: str,
    locked_statement: str,
    candidate_source: str,
    *,
    imports: tuple[str, ...] = (),
    preamble: str = "",
    allow_sorry: bool = False,
) -> str:
    """Lock target proposition outside `_PathWeaverCandidate` namespace so helpers are allowed safely."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_'.]*", theorem_name):
        raise ValueError(f"Invalid Lean theorem identifier: {theorem_name!r}")
    src_errors = audit_formal_source(candidate_source, backend="lean4", allow_sorry=allow_sorry)
    if src_errors:
        raise ValueError("; ".join(src_errors))
    cleaned = _strip_lean_comments_and_strings(candidate_source)
    for pattern, reason in (
        (r"(?m)^\s*import\b", "candidate cannot declare import statements"),
        (r"(?m)^\s*#print\b", "candidate cannot invoke #print"),
        (r"(?m)^\s*set_option\b", "candidate cannot alter Lean options"),
        (r"\b_PathWeaver", "reserved PathWeaver identifier"),
        (r"\b_pathweaver_", "reserved PathWeaver identifier"),
        (r"\bopen\s+Lean\b", "candidate cannot open Lean internals"),
    ):
        if re.search(pattern, cleaned):
            raise ValueError(reason)

    prop_type = _statement_to_prop_type(locked_statement)
    stmt_decl = locked_statement.strip()
    if not stmt_decl.startswith(":") and not re.match(r"^[\(\{\[]", stmt_decl):
        stmt_decl = f": {prop_type}"
    has_theorem_decl = bool(re.search(rf"\b(?:theorem|lemma)\s+{re.escape(theorem_name)}\b", cleaned))

    lines = [f"import {imp}" for imp in imports]
    if lines:
        lines.append("")
    if preamble.strip():
        lines.extend(["-- TRUSTED PREAMBLE", preamble.rstrip(), ""])
    lines.extend([
        f"private abbrev _PathWeaverTargetProp : Prop := ({prop_type})",
        "",
        "namespace _PathWeaverCandidate",
    ])
    if has_theorem_decl:
        lines.append(candidate_source.rstrip())
    else:
        lines.append(f"theorem {theorem_name} {stmt_decl} := by")
        lines.extend(f"  {line}" if line.strip() else "" for line in candidate_source.splitlines())
    lines.extend([
        "end _PathWeaverCandidate",
        "",
        f"theorem _pathweaver_verified_target : _PathWeaverTargetProp := @_PathWeaverCandidate.{theorem_name}",
        "#print axioms _pathweaver_verified_target",
        "",
    ])
    return "\n".join(lines)


def _parse_lean_json_output(stdout: str, stderr: str) -> tuple[list[dict[str, Any]], str]:
    """Parse `lean --json` lines into structured diagnostics plus human-readable text."""
    diagnostics: list[dict[str, Any]] = []
    text_lines: list[str] = []
    for raw_line in stdout.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            text_lines.append(raw_line)
            continue
        if isinstance(obj, dict) and "severity" in obj and "data" in obj:
            pos = obj.get("pos") or {}
            line_no = pos.get("line") if isinstance(pos, dict) else None
            col_no = pos.get("column") if isinstance(pos, dict) else None
            severity = str(obj.get("severity", "information"))
            message = str(obj.get("data", "")).strip()
            diagnostics.append({"severity": severity, "line": line_no, "column": col_no, "message": message})
            loc = f"{line_no}:{col_no}: " if line_no is not None else ""
            text_lines.append(f"{severity}: {loc}{message}")
        else:
            text_lines.append(raw_line)
    if stderr.strip():
        text_lines.append(stderr.strip())
    return diagnostics, "\n".join(text_lines).strip()


def _parse_lean_axioms(
    output: str,
    theorem_name: str,
    *,
    allowed_axioms: frozenset[str] = ALLOWED_LEAN_AXIOMS,
) -> tuple[list[str], list[str]]:
    """Extract `#print axioms` output and reject unexpected or sorry axioms."""
    match = re.search(rf"'{re.escape(theorem_name)}'\s+depends on axioms:\s*\[([^\]]*)\]", output)
    if not match:
        if f"'{theorem_name}' does not depend on any axioms" in output:
            return [], []
        return [], [f"Missing `#print axioms {theorem_name}` confirmation in Lean output"]
    axioms = [item.strip() for item in match.group(1).split(",") if item.strip()]
    errors = [f"Disallowed axiom in kernel trace: {ax}" for ax in axioms if ax not in allowed_axioms]
    return axioms, errors


def _build_lean_command(
    target_path: Path,
    *,
    effective_project: str | Path | None,
    docker_image: str | None,
) -> tuple[list[str], Path] | str:
    """Return `(cmd, cwd)` or an unavailable-reason string."""
    if docker_image:
        if not shutil.which("docker"):
            return "Docker CLI not found for containerized Lean verification"
        cmd = [
            "docker", "run", "--rm", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "-v", f"{target_path.parent}:/work:ro",
            docker_image,
            "lean", "--json", f"/work/{target_path.name}",
        ]
        return cmd, target_path.parent

    lean_bin = resolve_lean_executable("lean")
    lake_bin = resolve_lean_executable("lake")
    if effective_project is not None and lake_bin is not None:
        return [lake_bin, "env", lean_bin or "lean", "--json", str(target_path)], Path(effective_project).resolve()
    if lean_bin is not None:
        return [lean_bin, "--json", str(target_path)], target_path.parent
    return "Neither `lean` nor `lake` executable found on PATH or in ~/.elan/bin"


def verify_formal_proof(
    source: str,
    *,
    backend: str = "lean4",
    theorem_name: str | None = None,
    project_dir: str | Path | None = None,
    docker_image: str | None = None,
    timeout_seconds: float = 60.0,
    allowed_axioms: frozenset[str] = ALLOWED_LEAN_AXIOMS,
    allow_partial_sorry: bool = False,
) -> FormalVerificationResult:
    """Run Lean 4 kernel verification with soundness and `#print axioms` checks; fail closed if unavailable."""
    started = time.monotonic()
    source_hash = digest(source.encode("utf-8"))
    normalized = source.lstrip("\ufeff")

    def _elapsed() -> float:
        return round(time.monotonic() - started, 6)

    soundness_errors = audit_formal_source(normalized, backend=backend, allow_sorry=allow_partial_sorry)
    if soundness_errors:
        return FormalVerificationResult(
            status="rejected_soundness", backend=backend, theorem_name=theorem_name,
            source_sha256=source_hash, soundness_errors=tuple(soundness_errors), wall_seconds=_elapsed(),
        )

    check_source = normalized
    if theorem_name and not re.search(
        rf"(?m)^\s*#print\s+axioms\s+{re.escape(theorem_name)}\b",
        _strip_lean_comments_and_strings(check_source),
    ):
        check_source = check_source.rstrip() + f"\n\n#print axioms {theorem_name}\n"

    effective_project = project_dir
    if effective_project is None and "PathWeaverFormal" in check_source:
        effective_project = default_formal_project_dir()

    with tempfile.TemporaryDirectory(prefix="pathweaver-formal-") as tmpdir:
        target_path = Path(tmpdir) / "Check.lean"
        target_path.write_text(check_source, encoding="utf-8", newline="\n")

        resolved = _build_lean_command(target_path, effective_project=effective_project, docker_image=docker_image)
        if isinstance(resolved, str):
            return FormalVerificationResult(
                status="backend_unavailable", backend=backend, theorem_name=theorem_name,
                source_sha256=source_hash, compiler_output=resolved, wall_seconds=_elapsed(),
            )
        cmd, cwd = resolved

        try:
            proc = _run_subprocess(cmd, cwd=cwd, timeout=timeout_seconds)
        except (OSError, subprocess.TimeoutExpired) as error:
            return FormalVerificationResult(
                status="failed", backend=backend, theorem_name=theorem_name,
                source_sha256=source_hash, compiler_output=f"Lean execution failed: {error}", wall_seconds=_elapsed(),
            )

        diagnostics, combined_out = _parse_lean_json_output(proc.stdout, proc.stderr)
        error_count = sum(1 for item in diagnostics if item["severity"] == "error")
        sorry_count = sum(
            1 for item in diagnostics
            if item["severity"] == "warning" and "sorry" in item["message"].lower()
        )

        if proc.returncode != 0 or error_count > 0:
            return FormalVerificationResult(
                status="failed", backend=backend, theorem_name=theorem_name,
                source_sha256=source_hash, compiler_output=combined_out[:4000],
                diagnostics=tuple(diagnostics),
                error_count=max(error_count, 1 if proc.returncode != 0 else 0),
                sorry_count=sorry_count, wall_seconds=_elapsed(),
            )

        axioms: list[str] = []
        post_errors: list[str] = []
        if theorem_name:
            axioms, ax_errors = _parse_lean_axioms(combined_out, theorem_name, allowed_axioms=allowed_axioms)
            post_errors.extend(ax_errors)
        if "sorryAx" in axioms:
            sorry_count = max(sorry_count, 1)
        if sorry_count > 0 and not any("sorry" in msg.lower() for msg in post_errors):
            post_errors.append("Lean proof relies on `sorry` / `sorryAx`")

        if post_errors:
            only_sorry = (
                allow_partial_sorry
                and sorry_count > 0
                and all("sorry" in err.lower() for err in post_errors)
                and all(ax in allowed_axioms or ax == "sorryAx" for ax in axioms)
            )
            return FormalVerificationResult(
                status="incomplete_sorry" if only_sorry else "rejected_soundness",
                backend=backend, theorem_name=theorem_name, source_sha256=source_hash,
                axioms=tuple(axioms), soundness_errors=tuple(post_errors),
                compiler_output=combined_out[:4000], diagnostics=tuple(diagnostics),
                error_count=0, sorry_count=sorry_count, wall_seconds=_elapsed(),
            )

        return FormalVerificationResult(
            status="verified", backend=backend, theorem_name=theorem_name,
            source_sha256=source_hash, axioms=tuple(axioms),
            compiler_output=combined_out[:4000], diagnostics=tuple(diagnostics),
            error_count=0, sorry_count=0, wall_seconds=_elapsed(),
        )
