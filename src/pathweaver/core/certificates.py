"""Domain-neutral Branch-and-Bound, LRAT/RUP, VIPR MILP, and Nullstellensatz proof kernels."""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
import gzip
import math
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class CertificateOutcome:
    """Minimal outcome emitted by the domain-neutral BnB proof-tree kernel."""

    status: str  # "verified" | "rejected"
    verified_nodes: int = 0
    reason: str | None = None


def verify_bnb_proof_tree(
    tree: Mapping[str, Any],
    *,
    root_state: Any,
    apply_branch: Callable[[Any, Any, int], Any],
    lower_bound_fn: Callable[[Any], int],
    is_infeasible_fn: Callable[[Any], bool],
    evaluate_leaf_fn: Callable[[Any, Mapping[str, Any]], int],
    incumbent_objective: int,
    max_nodes: int = 250_000,
) -> CertificateOutcome:
    """Independently verify an exhaustive binary Branch-and-Bound optimality proof tree.

    Internal ``branch`` nodes must cover both ``include`` (1) and ``exclude`` (0).
    Leaves must be proved ``infeasible``, ``pruned_by_bound`` (``lb >= incumbent``),
    or ``incumbent`` (feasible value >= incumbent, with >=1 leaf attaining it exactly).
    """
    if not isinstance(tree, Mapping):
        return CertificateOutcome(status="rejected", reason="Proof tree must be an object")

    visited = 0
    matched_incumbent = False
    stack: list[tuple[Mapping[str, Any], Any]] = [(tree, root_state)]
    try:
        while stack:
            node, state = stack.pop()
            visited += 1
            if visited > max_nodes:
                raise ValueError(f"Proof tree exceeds node limit ({max_nodes})")
            if not isinstance(node, Mapping):
                raise ValueError("Proof node must be a mapping")
            kind = node.get("kind")
            if kind == "branch":
                var, left, right = node.get("var"), node.get("include"), node.get("exclude")
                if var is None or left is None or right is None:
                    raise ValueError("Branch node must specify var, include, and exclude children")
                stack.append((left, apply_branch(state, var, 1)))
                stack.append((right, apply_branch(state, var, 0)))
            elif kind == "infeasible":
                if not is_infeasible_fn(state):
                    raise ValueError("Leaf marked infeasible is not independently infeasible")
            elif kind == "pruned_by_bound":
                lb = lower_bound_fn(state)
                if type(lb) is not int or lb < incumbent_objective:
                    raise ValueError(f"Pruned leaf lower bound {lb} < incumbent {incumbent_objective}")
            elif kind == "incumbent":
                leaf_val = evaluate_leaf_fn(state, node)
                if type(leaf_val) is not int or leaf_val < incumbent_objective:
                    raise ValueError(f"Incumbent leaf value {leaf_val} < declared incumbent {incumbent_objective}")
                if leaf_val == incumbent_objective:
                    matched_incumbent = True
            else:
                raise ValueError(f"Unknown proof-tree node kind: {kind!r}")

        if not matched_incumbent:
            raise ValueError("Proof tree has no leaf attaining the declared incumbent objective")
    except (ValueError, TypeError, KeyError) as error:
        return CertificateOutcome(status="rejected", reason=str(error))

    return CertificateOutcome(status="verified", verified_nodes=visited)


_LEAN_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_']*$")


def _strict_int(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer (got {type(value).__name__})")
    return value


def _parse_int_token(token: str, name: str) -> int:
    try:
        return int(token, 10)
    except ValueError as error:
        raise ValueError(f"Invalid integer token for {name}: {token!r}") from error


def _to_fraction(value: Any, name: str) -> Fraction:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{name} must be an exact int, str, or Fraction (got {type(value).__name__})")
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{name} cannot be an empty numeric string")
        try:
            return Fraction(text)
        except ValueError as error:
            raise ValueError(f"Invalid exact rational for {name}: {value!r}") from error
    raise ValueError(f"{name} must be an exact int, str, or Fraction (got {type(value).__name__})")


def _validate_cnf_clauses(clauses: Sequence[Sequence[int]]) -> list[tuple[int, ...]]:
    if isinstance(clauses, (str, bytes)) or not isinstance(clauses, Sequence):
        raise ValueError("clauses must be a sequence of integer literal clauses")
    parsed: list[tuple[int, ...]] = []
    for idx, clause in enumerate(clauses, start=1):
        if isinstance(clause, (str, bytes)) or not isinstance(clause, Sequence):
            raise ValueError(f"Clause {idx} must be a sequence of integers")
        lits: list[int] = []
        for lit in clause:
            val = _strict_int(lit, f"clause {idx} literal")
            if val == 0:
                raise ValueError(f"Clause {idx} contains invalid literal 0")
            lits.append(val)
        parsed.append(tuple(lits))
    return parsed


def _read_lrat_lines(source: str | Path) -> list[str]:
    if isinstance(source, str) and "\n" in source:
        return source.splitlines()
    path = Path(source)
    if not path.is_file():
        raise ValueError(f"LRAT proof file does not exist: {path.name}")
    with path.open("rb") as probe:
        magic = probe.read(2)
    is_gz = path.suffix == ".gz" or magic == b"\x1f\x8b"
    if is_gz:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return stream.read().splitlines()
    return path.read_text(encoding="utf-8").splitlines()


def _parse_lrat_events(
    proof: str | Path | Sequence[tuple[int, Sequence[int], Sequence[int]]],
) -> list[tuple[str, int, tuple[int, ...], tuple[int, ...]]]:
    events: list[tuple[str, int, tuple[int, ...], tuple[int, ...]]] = []
    if isinstance(proof, (str, Path)):
        for line_no, raw_line in enumerate(_read_lrat_lines(proof), start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("c"):
                continue
            parts = stripped.split()
            if len(parts) < 3:
                raise ValueError(f"Malformed LRAT line {line_no}: too few tokens")
            step_id = _parse_int_token(parts[0], f"line {line_no} step id")
            if step_id < 1:
                raise ValueError(f"LRAT line {line_no} step id must be >= 1")
            if parts[1] == "d":
                if parts[-1] != "0":
                    raise ValueError(f"LRAT deletion line {line_no} must terminate with 0")
                deleted = tuple(_parse_int_token(tok, f"line {line_no} deleted id") for tok in parts[2:-1])
                if any(cid < 1 for cid in deleted):
                    raise ValueError(f"LRAT deletion line {line_no} contains invalid clause id")
                events.append(("delete", step_id, deleted, ()))
                continue
            try:
                zero1 = parts.index("0", 1)
                zero2 = parts.index("0", zero1 + 1)
            except ValueError as error:
                raise ValueError(f"Malformed LRAT addition line {line_no}: missing 0 terminator") from error
            if zero2 != len(parts) - 1:
                raise ValueError(f"Malformed LRAT addition line {line_no}: trailing tokens after second 0")
            lits = tuple(_parse_int_token(tok, f"line {line_no} literal") for tok in parts[1:zero1])
            if any(lit == 0 for lit in lits):
                raise ValueError(f"LRAT line {line_no} contains invalid literal 0")
            hints = tuple(_parse_int_token(tok, f"line {line_no} hint") for tok in parts[zero1 + 1 : zero2])
            if any(hid <= 0 for hid in hints):
                raise ValueError(f"LRAT line {line_no} contains non-positive RAT/invalid hint")
            events.append(("add", step_id, lits, hints))
        return events

    if isinstance(proof, (bytes, bytearray)) or not isinstance(proof, Sequence):
        raise ValueError("proof must be a file path, LRAT text, or sequence of (id, clause, hints) tuples")
    for idx, step in enumerate(proof, start=1):
        if isinstance(step, (str, bytes)) or not isinstance(step, Sequence) or len(step) != 3:
            raise ValueError(f"Proof step {idx} must be a (id, clause, hints) triple")
        step_id = _strict_int(step[0], f"step {idx} id")
        if step_id < 1:
            raise ValueError(f"Proof step {idx} id must be >= 1")
        raw_clause, raw_hints = step[1], step[2]
        if isinstance(raw_clause, (str, bytes)) or not isinstance(raw_clause, Sequence):
            raise ValueError(f"Proof step {idx} clause must be a sequence of integers")
        if isinstance(raw_hints, (str, bytes)) or not isinstance(raw_hints, Sequence):
            raise ValueError(f"Proof step {idx} hints must be a sequence of positive integers")
        lits = tuple(_strict_int(lit, f"step {idx} literal") for lit in raw_clause)
        if any(lit == 0 for lit in lits):
            raise ValueError(f"Proof step {idx} clause contains invalid literal 0")
        hints = tuple(_strict_int(hid, f"step {idx} hint") for hid in raw_hints)
        if any(hid <= 0 for hid in hints):
            raise ValueError(f"Proof step {idx} hints must be positive integers")
        events.append(("add", step_id, lits, hints))
    return events


def _has_complementary_literals(clause: Sequence[int]) -> bool:
    seen = set(clause)
    return any(lit != 0 and -lit in seen for lit in seen)


def verify_lrat_unsat(
    clauses: Sequence[Sequence[int]],
    proof: str | Path | Sequence[tuple[int, Sequence[int], Sequence[int]]],
) -> CertificateOutcome:
    """Verify a positive-hint RUP/LRAT refutation against a CNF clause sequence."""
    added = 0
    try:
        parsed_clauses = _validate_cnf_clauses(clauses)
        events = _parse_lrat_events(proof)
        active: dict[int, tuple[int, ...]] = {
            cid: clause for cid, clause in enumerate(parsed_clauses, start=1)
        }
        last_id = len(parsed_clauses)
        derived_empty = False

        for kind, step_id, lits, hints in events:
            if kind == "delete":
                for cid in lits:
                    active.pop(cid, None)
                continue

            if step_id <= last_id:
                raise ValueError(f"LRAT step id {step_id} must exceed previous id {last_id}")

            if not _has_complementary_literals(lits):
                falsified = set(lits)
                conflict = False
                for hid in hints:
                    hint_clause = active.get(hid)
                    if hint_clause is None:
                        raise ValueError(f"Step {step_id} references unknown or deleted clause id {hid}")
                    remaining = {lit for lit in hint_clause if lit not in falsified}
                    if not remaining:
                        conflict = True
                        break
                    if len(remaining) == 1:
                        falsified.add(-next(iter(remaining)))
                    else:
                        raise ValueError(
                            f"Step {step_id} hint {hid} is non-unit ({len(remaining)} un-falsified literals)"
                        )
                if not conflict:
                    raise ValueError(f"Step {step_id} failed to derive a RUP conflict")

            active[step_id] = lits
            last_id = step_id
            added += 1
            if len(lits) == 0:
                derived_empty = True

        if not derived_empty:
            raise ValueError("LRAT refutation did not derive the empty clause []")
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        return CertificateOutcome(status="rejected", verified_nodes=added, reason=str(error))

    return CertificateOutcome(status="verified", verified_nodes=added)


def trim_lrat_proof(
    input_count: int,
    raw_path: str | Path,
    gzip_path: str | Path,
) -> int:
    """Backward-trim an LRAT proof to empty-clause dependencies and write compressed .lrat.gz."""
    _strict_int(input_count, "input_count")
    if input_count < 0:
        raise ValueError("input_count must be >= 0")

    events = _parse_lrat_events(Path(raw_path))
    steps: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    known_ids = set(range(1, input_count + 1))
    last_id = input_count
    empty_idx: int | None = None

    for kind, step_id, lits, hints in events:
        if kind == "delete":
            continue
        if step_id <= last_id:
            raise ValueError(f"LRAT step id {step_id} must exceed previous id {last_id}")
        for hid in hints:
            if hid not in known_ids:
                raise ValueError(f"Step {step_id} references unknown hint clause id {hid}")
        steps.append((step_id, lits, hints))
        known_ids.add(step_id)
        last_id = step_id
        if empty_idx is None and len(lits) == 0:
            empty_idx = len(steps) - 1

    if empty_idx is None:
        raise ValueError("Raw LRAT proof does not derive the empty clause []")

    needed: set[int] = {steps[empty_idx][0]}
    kept_rev: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for step_id, lits, hints in reversed(steps[: empty_idx + 1]):
        if step_id in needed:
            kept_rev.append((step_id, lits, hints))
            for hid in hints:
                if hid > input_count:
                    needed.add(hid)

    kept = list(reversed(kept_rev))
    remap = {old_id: input_count + idx for idx, (old_id, _, _) in enumerate(kept, start=1)}
    lines: list[str] = []
    for old_id, lits, hints in kept:
        new_id = remap[old_id]
        remapped_hints = [remap[hid] if hid > input_count else hid for hid in hints]
        tokens = [str(new_id), *(str(lit) for lit in lits), "0", *(str(hid) for hid in remapped_hints), "0"]
        lines.append(" ".join(tokens))

    dest = Path(gzip_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wt", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + ("\n" if lines else ""))
    return len(kept)


def export_rup_lean_certificate(
    clauses: Sequence[Sequence[int]],
    rup_steps: Sequence[tuple[int, Sequence[int], Sequence[int]]],
    *,
    theorem_name: str = "sat_unsat_certified",
) -> dict[str, Any]:
    """Verify a RUP refutation and emit a kernel-checked Lean 4 certificate using LratBridge."""
    if not isinstance(theorem_name, str) or not _LEAN_IDENT_RE.match(theorem_name):
        raise ValueError(f"Invalid Lean theorem identifier: {theorem_name!r}")

    outcome = verify_lrat_unsat(clauses, rup_steps)
    if outcome.status != "verified":
        raise ValueError(f"Cannot export Lean certificate for invalid RUP refutation: {outcome.reason}")

    parsed_clauses = _validate_cnf_clauses(clauses)
    lean_clauses = "[" + ", ".join("[" + ", ".join(str(l) for l in c) + "]" for c in parsed_clauses) + "]"
    lean_steps = [
        f"  {{ id := {int(sid)}, clause := [{', '.join(str(int(l)) for l in cl)}], "
        f"hints := [{', '.join(str(int(h)) for h in hs)}] }}"
        for sid, cl, hs in rup_steps
    ]
    steps_block = "[\n" + ",\n".join(lean_steps) + "\n]" if lean_steps else "[]"

    lean_source = "\n".join([
        "import PathWeaverFormal.LratBridge",
        "",
        f"def F : PathWeaverFormal.LratBridge.CnfFormula := {lean_clauses}",
        "",
        f"def rupSteps : List PathWeaverFormal.LratBridge.RupStep := {steps_block}",
        "",
        f"theorem {theorem_name} : ¬ PathWeaverFormal.LratBridge.CnfSatisfiable F :=",
        "  PathWeaverFormal.LratBridge.rup_chain_unsat F rupSteps (by decide)",
        "",
        f"#print axioms {theorem_name}",
        "",
    ])
    return {
        "theorem_name": theorem_name,
        "certificate_kind": "sat_rup_unsat_lean",
        "num_clauses": len(parsed_clauses),
        "num_steps": len(rup_steps),
        "lean_source": lean_source,
    }


def _parse_index_key(key: int | str, limit: int, label: str) -> int:
    if type(key) is int:
        idx = key
    elif isinstance(key, str):
        idx = _parse_int_token(key.strip(), label)
    else:
        raise ValueError(f"{label} key must be int or numeric str (got {type(key).__name__})")
    if not (0 <= idx < limit):
        raise ValueError(f"{label} index {idx} out of range [0, {limit - 1}]")
    return idx


def verify_vipr_milp_bound(
    num_vars: int,
    constraints: Sequence[Mapping[str, Any]],
    objective: Sequence[int | str],
    dual_multipliers: Mapping[int | str, int | str],
    claimed_lower_bound: int | str,
    *,
    var_lower_bounds: Sequence[int | str] | None = None,
    integer_vars: Sequence[int] = (),
    cg_round: bool = False,
) -> CertificateOutcome:
    """Verify an exact rational LP/MILP dual lower bound (VIPR-style), with optional CG rounding."""
    try:
        _strict_int(num_vars, "num_vars")
        if num_vars < 0:
            raise ValueError("num_vars must be >= 0")
        if isinstance(constraints, (str, bytes)) or not isinstance(constraints, Sequence):
            raise ValueError("constraints must be a sequence of mappings")
        if isinstance(objective, (str, bytes)) or not isinstance(objective, Sequence) or len(objective) != num_vars:
            raise ValueError(f"objective must be a sequence of length {num_vars}")
        if not isinstance(dual_multipliers, Mapping):
            raise ValueError("dual_multipliers must be a mapping")

        obj = [_to_fraction(val, f"objective[{j}]") for j, val in enumerate(objective)]
        claimed_lb = _to_fraction(claimed_lower_bound, "claimed_lower_bound")

        int_var_set: set[int] = set()
        for var_idx in integer_vars:
            j = _strict_int(var_idx, "integer_vars entry")
            if not (0 <= j < num_vars):
                raise ValueError(f"integer_vars index {j} out of range [0, {num_vars - 1}]")
            int_var_set.add(j)

        if cg_round and len(int_var_set) != num_vars:
            raise ValueError("cg_round=True requires every variable index in [0, num_vars-1] to be in integer_vars")

        if var_lower_bounds is None:
            lbs: list[Fraction | None] = [Fraction(0)] * num_vars
        else:
            if isinstance(var_lower_bounds, (str, bytes)) or not isinstance(var_lower_bounds, Sequence):
                raise ValueError("var_lower_bounds must be a sequence or None")
            if len(var_lower_bounds) != num_vars:
                raise ValueError(f"var_lower_bounds must have length {num_vars}")
            lbs = [
                None if lb is None else _to_fraction(lb, f"var_lower_bounds[{j}]")
                for j, lb in enumerate(var_lower_bounds)
            ]

        y_map: dict[int, Fraction] = {}
        for raw_key, raw_mult in dual_multipliers.items():
            idx = _parse_index_key(raw_key, len(constraints), "dual_multipliers")
            if idx in y_map:
                raise ValueError(f"Duplicate dual multiplier for constraint {idx}")
            y_map[idx] = _to_fraction(raw_mult, f"dual_multipliers[{raw_key!r}]")

        w = [Fraction(0)] * num_vars
        rhs_comb = Fraction(0)
        for i, con in enumerate(constraints):
            if not isinstance(con, Mapping):
                raise ValueError(f"Constraint {i} must be a mapping")
            sense = con.get("sense")
            if sense not in {">=", "<=", "="}:
                raise ValueError(f"Constraint {i} has invalid sense {sense!r}; expected '>=', '<=', or '='")
            if "rhs" not in con or "coeffs" not in con:
                raise ValueError(f"Constraint {i} must specify 'sense', 'coeffs', and 'rhs'")

            y_i = y_map.get(i, Fraction(0))
            if sense == ">=" and y_i < 0:
                raise ValueError(f"Constraint {i} ('>=') has negative dual multiplier {y_i}")
            if sense == "<=" and y_i > 0:
                raise ValueError(f"Constraint {i} ('<=') has positive dual multiplier {y_i}")

            b_i = _to_fraction(con["rhs"], f"constraints[{i}].rhs")
            rhs_comb += y_i * b_i

            coeffs = con["coeffs"]
            if isinstance(coeffs, Mapping):
                for raw_j, aval in coeffs.items():
                    j = _parse_index_key(raw_j, num_vars, f"constraints[{i}].coeffs")
                    w[j] += y_i * _to_fraction(aval, f"constraints[{i}].coeffs[{raw_j!r}]")
            elif not isinstance(coeffs, (str, bytes)) and isinstance(coeffs, Sequence):
                if len(coeffs) != num_vars:
                    raise ValueError(f"Constraint {i} coeffs list must have length {num_vars}")
                for j, aval in enumerate(coeffs):
                    w[j] += y_i * _to_fraction(aval, f"constraints[{i}].coeffs[{j}]")
            else:
                raise ValueError(f"Constraint {i} coeffs must be a mapping or sequence")

        if cg_round:
            shift = Fraction(0)
            for j in range(num_vars):
                w_ceil = Fraction(math.ceil(w[j]))
                lb_j = lbs[j]
                if lb_j is None:
                    if w_ceil != w[j]:
                        raise ValueError(
                            f"Cannot apply CG rounding to fractional coefficient {w[j]} on lower-unbounded var {j}"
                        )
                else:
                    shift += (w_ceil - w[j]) * lb_j
                w[j] = w_ceil
            rhs_comb = Fraction(math.ceil(rhs_comb + shift))

        total_lb = rhs_comb
        for j in range(num_vars):
            c_j = obj[j]
            lb_j = lbs[j]
            if lb_j is None:
                if w[j] != c_j:
                    raise ValueError(f"Free variable {j} dual equality violated: {w[j]} != {c_j}")
            else:
                if w[j] > c_j:
                    raise ValueError(f"Dual dominance violated at variable {j}: {w[j]} > {c_j}")
                total_lb += (c_j - w[j]) * lb_j

        if total_lb < claimed_lb:
            raise ValueError(f"Certified dual lower bound {total_lb} < claimed lower bound {claimed_lb}")
    except (ValueError, TypeError, KeyError) as error:
        return CertificateOutcome(status="rejected", reason=str(error))

    return CertificateOutcome(status="verified", verified_nodes=len(constraints))


def _to_ring_coeff(value: Any, modulus: int | None, name: str) -> int | Fraction:
    frac = _to_fraction(value, name)
    if modulus is None:
        return frac
    if frac.denominator == 1:
        return frac.numerator % modulus
    if math.gcd(frac.denominator, modulus) != 1:
        raise ValueError(f"{name} denominator {frac.denominator} is not invertible modulo {modulus}")
    return (frac.numerator * pow(frac.denominator, -1, modulus)) % modulus


def _parse_sparse_poly(
    poly: Mapping[tuple[int, ...], int | str],
    *,
    num_vars: int,
    modulus: int | None,
    label: str,
) -> dict[tuple[int, ...], int | Fraction]:
    if not isinstance(poly, Mapping):
        raise ValueError(f"{label} must be a mapping from exponent tuples to coefficients")
    parsed: dict[tuple[int, ...], int | Fraction] = {}
    for exp, raw_coeff in poly.items():
        if not isinstance(exp, tuple) or len(exp) != num_vars:
            raise ValueError(f"{label} monomial exponent {exp!r} must be a tuple of length {num_vars}")
        for deg in exp:
            _strict_int(deg, f"{label} exponent")
            if deg < 0:
                raise ValueError(f"{label} monomial exponent {exp!r} contains negative degree")
        coeff = _to_ring_coeff(raw_coeff, modulus, f"{label}[{exp!r}]")
        if coeff != 0:
            parsed[exp] = coeff
    return parsed


def verify_nullstellensatz_obstruction(
    polynomials: Sequence[Mapping[tuple[int, ...], int | str]],
    cofactors: Sequence[Mapping[tuple[int, ...], int | str]],
    *,
    num_vars: int,
    modulus: int | None = None,
) -> CertificateOutcome:
    """Verify exact Hilbert Nullstellensatz certificate sum_k c_k(x) * f_k(x) == 1 over Q or Z/mZ."""
    try:
        _strict_int(num_vars, "num_vars")
        if num_vars < 0:
            raise ValueError("num_vars must be >= 0")
        if modulus is not None:
            _strict_int(modulus, "modulus")
            if modulus < 2:
                raise ValueError("modulus must be >= 2 when provided")
        if isinstance(polynomials, (str, bytes)) or not isinstance(polynomials, Sequence):
            raise ValueError("polynomials must be a sequence of sparse polynomial mappings")
        if isinstance(cofactors, (str, bytes)) or not isinstance(cofactors, Sequence):
            raise ValueError("cofactors must be a sequence of sparse polynomial mappings")
        if len(polynomials) != len(cofactors):
            raise ValueError(
                f"polynomials length ({len(polynomials)}) must match cofactors length ({len(cofactors)})"
            )

        total: dict[tuple[int, ...], int | Fraction] = {}
        for k, (raw_poly, raw_cof) in enumerate(zip(polynomials, cofactors)):
            poly = _parse_sparse_poly(raw_poly, num_vars=num_vars, modulus=modulus, label=f"polynomials[{k}]")
            cof = _parse_sparse_poly(raw_cof, num_vars=num_vars, modulus=modulus, label=f"cofactors[{k}]")
            for exp_c, coeff_c in cof.items():
                for exp_p, coeff_p in poly.items():
                    exp = tuple(a + b for a, b in zip(exp_c, exp_p, strict=True))
                    prod = coeff_c * coeff_p
                    updated = total.get(exp, 0 if modulus is not None else Fraction(0)) + prod
                    if modulus is not None:
                        updated %= modulus
                    if updated == 0:
                        total.pop(exp, None)
                    else:
                        total[exp] = updated

        one_exp = (0,) * num_vars
        expected_one: int | Fraction = 1 if modulus is not None else Fraction(1)
        if total != {one_exp: expected_one}:
            const_term = total.get(one_exp, 0)
            extra_terms = [exp for exp in total if exp != one_exp]
            raise ValueError(
                f"Nullstellensatz combination != 1 (constant_term={const_term}, non_constant_terms={len(extra_terms)})"
            )
    except (ValueError, TypeError, KeyError) as error:
        return CertificateOutcome(status="rejected", reason=str(error))

    return CertificateOutcome(status="verified", verified_nodes=len(polynomials))

