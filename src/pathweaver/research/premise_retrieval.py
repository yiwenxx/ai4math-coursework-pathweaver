"""Offline Lean 4 premise index (BM25 + Loogle-style matching) and integer sequence / OEIS recognizer."""
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from fractions import Fraction
import math
from pathlib import Path
import re
import threading
from typing import Any

from pathweaver.research.formal_verifier import (
    _strip_lean_comments_and_strings,
    default_formal_project_dir,
)

_DECL_KINDS = ("theorem", "lemma", "def", "abbrev", "structure")
_DECL_HEADER_RE = re.compile(
    r"^(?P<vis>(?:(?:private|protected|noncomputable|unsafe|partial)\s+)*)"
    r"(?P<kind>theorem|lemma|def|abbrev|structure)\s+"
    r"(?P<name>[^\s:({\[<]+)"
)
_NS_RE = re.compile(
    r"^(?:namespace\s+(?P<ns>[A-Za-z_][A-Za-z0-9_'.]*)"
    r"|(?P<sec>(?:noncomputable\s+)?section)(?:\s+[A-Za-z_][A-Za-z0-9_'.]*)?"
    r"|(?P<end>end)(?:\s+[A-Za-z_][A-Za-z0-9_'.]*)?)\s*$"
)
_DOC_START_RE = re.compile(r"^\s*/--(.*)$")
_DOC_END_RE = re.compile(r"(.*?)-/\s*$")
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_']+|→|->|∀|∃|≤|≥|≠|∧|∨|↔|⊢|[=<>+%*]")


@dataclass(frozen=True)
class PremiseEntry:
    name: str
    kind: str
    module: str
    signature: str
    docstring: str
    file_path: str
    line: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _tokenize_identifier_parts(token: str) -> list[str]:
    parts: list[str] = []
    for chunk in re.split(r"[_.]+", token):
        if not chunk:
            continue
        for sub in _CAMEL_SPLIT_RE.split(chunk):
            low = sub.strip("'").lower()
            if low:
                parts.append(low)
    return parts


def _tokenize_text(text: str) -> list[str]:
    normalized = text.replace("->", "→")
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(normalized):
        if raw in {"→", "∀", "∃", "≤", "≥", "≠", "∧", "∨", "↔", "⊢", "=", "<", ">", "+", "%", "*"}:
            tokens.append(raw)
        else:
            low = raw.lower()
            tokens.append(low)
            sub = _tokenize_identifier_parts(raw)
            if len(sub) > 1:
                tokens.extend(sub)
    return tokens


def _extract_signature_end(lines: list[str], start_idx: int) -> str:
    """Collect a declaration header/signature starting at `start_idx` up to top-level `:=`, `where`, or `|`."""
    collected: list[str] = []
    depth = 0
    in_block_comment = 0
    in_string = False

    for idx in range(start_idx, min(len(lines), start_idx + 40)):
        line = lines[idx]
        if idx > start_idx and depth == 0 and line.lstrip().startswith("|"):
            break
        n = len(line)
        i = 0
        stop_pos: int | None = None
        while i < n:
            ch = line[i]
            nxt = line[i : i + 2]
            if in_block_comment > 0:
                if nxt == "/-":
                    in_block_comment += 1
                    i += 2
                elif nxt == "-/":
                    in_block_comment -= 1
                    i += 2
                else:
                    i += 1
                continue
            if in_string:
                if ch == "\\" and i + 1 < n:
                    i += 2
                elif ch == '"':
                    in_string = False
                    i += 1
                else:
                    i += 1
                continue
            if nxt == "/-":
                in_block_comment = 1
                i += 2
                continue
            if nxt == "--":
                break
            if ch == '"':
                in_string = True
                i += 1
                continue
            if ch in "({[⟨":
                depth += 1
                i += 1
                continue
            if ch in ")}]⟩":
                depth = max(0, depth - 1)
                i += 1
                continue
            if depth == 0:
                if nxt == ":=":
                    stop_pos = i
                    break
                if line[i : i + 5] == "where" and (i == 0 or not line[i - 1].isalnum()) and (
                    i + 5 == n or not (line[i + 5].isalnum() or line[i + 5] == "_")
                ):
                    stop_pos = i
                    break
            i += 1

        if stop_pos is not None:
            collected.append(line[:stop_pos])
            break
        # Strip inline `--` comment when appending full line
        stripped_comment = _strip_lean_comments_and_strings(line) if "--" in line else line
        collected.append(stripped_comment)
        if depth == 0 and idx > start_idx:
            trimmed = line.strip()
            if not trimmed:
                break

    joined = " ".join(" ".join(collected).split())
    return joined[:500]


def _scan_lean_file(path: Path, module_root: Path) -> list[PremiseEntry]:
    raw_text = path.read_bytes().decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    lines = raw_text.split("\n")
    try:
        rel_path = path.resolve().relative_to(module_root.resolve())
        module_name = ".".join(rel_path.with_suffix("").parts)
        rel_posix = rel_path.as_posix()
    except ValueError:
        module_name = path.stem
        rel_posix = path.name

    entries: list[PremiseEntry] = []
    scopes: list[str] = []
    pending_doc: str = ""
    in_doc = False
    doc_lines: list[str] = []
    in_comment = 0

    for line_idx, raw_line in enumerate(lines):
        stripped = raw_line.strip()

        if in_doc:
            end_match = _DOC_END_RE.search(raw_line)
            if end_match:
                doc_lines.append(end_match.group(1).strip())
                pending_doc = " ".join(part for part in doc_lines if part).strip()
                doc_lines = []
                in_doc = False
            else:
                doc_lines.append(stripped)
            continue

        if in_comment > 0:
            if "/-" in raw_line:
                in_comment += raw_line.count("/-")
            if "-/" in raw_line:
                in_comment -= raw_line.count("-/")
            in_comment = max(0, in_comment)
            continue

        doc_start = _DOC_START_RE.match(raw_line)
        if doc_start:
            rest = doc_start.group(1)
            end_match = _DOC_END_RE.search(rest)
            if end_match:
                pending_doc = end_match.group(1).strip()
            else:
                in_doc = True
                doc_lines = [rest.strip()]
            continue

        if stripped.startswith("/-") and not stripped.startswith("/--"):
            opens = stripped.count("/-")
            closes = stripped.count("-/")
            in_comment = max(0, opens - closes)
            pending_doc = ""
            continue

        if not stripped or stripped.startswith("--"):
            continue
        if stripped.startswith("@["):
            continue

        ns_match = _NS_RE.match(stripped)
        if ns_match:
            if ns_match.group("ns"):
                scopes.append(ns_match.group("ns"))
            elif ns_match.group("sec"):
                scopes.append("")
            elif ns_match.group("end") and scopes:
                scopes.pop()
            pending_doc = ""
            continue

        decl_match = _DECL_HEADER_RE.match(stripped)
        if decl_match:
            vis = decl_match.group("vis") or ""
            kind = decl_match.group("kind")
            raw_name = decl_match.group("name")
            if "private" not in vis:
                if raw_name.startswith("_root_."):
                    full_name = raw_name.removeprefix("_root_.")
                else:
                    full_name = ".".join(part for part in [*scopes, raw_name] if part)
                sig = _extract_signature_end(lines, line_idx)
                entries.append(
                    PremiseEntry(
                        name=full_name,
                        kind=kind,
                        module=module_name,
                        signature=sig,
                        docstring=pending_doc,
                        file_path=rel_posix,
                        line=line_idx + 1,
                    )
                )
            pending_doc = ""
            continue

        # Any other non-attribute command resets pending docstrings
        if not stripped.startswith("#") and not stripped.startswith("open "):
            pending_doc = ""

    return entries


class PremiseIndex:
    """Offline index of Lean 4 declarations with BM25, Loogle-style type/symbol matching, and import boosts."""

    def __init__(self, project_dir: str | Path | None = None) -> None:
        if project_dir is None:
            root = default_formal_project_dir()
            if root is not None and (root / "PathWeaverFormal").is_dir():
                self.module_root: Path | None = root
                self.scan_dir: Path | None = root / "PathWeaverFormal"
            else:
                self.module_root = root
                self.scan_dir = root
        else:
            p = Path(project_dir).resolve()
            if (p / "PathWeaverFormal").is_dir() and (
                (p / "lakefile.toml").is_file()
                or (p / "lakefile.lean").is_file()
                or (p / "PathWeaverFormal.lean").is_file()
            ):
                self.module_root = p
                self.scan_dir = p / "PathWeaverFormal"
            else:
                self.scan_dir = p
                self.module_root = p.parent if p.name == "PathWeaverFormal" else p

        self.entries: list[PremiseEntry] = []
        self._doc_tokens: list[list[str]] = []
        self._doc_freqs: list[Counter[str]] = []
        self._idf: dict[str, float] = {}
        self._avgdl: float = 1.0
        self._build_index()

    def _build_index(self) -> None:
        if self.scan_dir is None or not self.scan_dir.is_dir():
            return
        module_root = self.module_root or self.scan_dir
        lean_files = sorted(
            path for path in self.scan_dir.rglob("*.lean")
            if ".lake" not in path.parts
        )
        for lean_file in lean_files:
            self.entries.extend(_scan_lean_file(lean_file, module_root))

        df: Counter[str] = Counter()
        total_len = 0
        for entry in self.entries:
            combined = f"{entry.name} {entry.module} {entry.signature} {entry.docstring}"
            tokens = _tokenize_text(combined)
            self._doc_tokens.append(tokens)
            tf = Counter(tokens)
            self._doc_freqs.append(tf)
            total_len += len(tokens)
            for tok in tf:
                df[tok] += 1

        n_docs = len(self.entries)
        self._avgdl = (total_len / n_docs) if n_docs > 0 else 1.0
        self._idf = {
            tok: math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))
            for tok, freq in df.items()
        }

    def search(
        self,
        query: str,
        *,
        imports: Sequence[str] = (),
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        if not self.entries or top_k <= 0:
            return []

        import_set = {imp.strip() for imp in imports if isinstance(imp, str) and imp.strip()}
        umbrella_imported = "PathWeaverFormal" in import_set
        q_stripped = (query or "").strip()
        q_tokens = _tokenize_text(q_stripped)
        q_unique = list(dict.fromkeys(q_tokens))
        q_lower = q_stripped.lower()
        arrow_clauses = [
            _tokenize_text(part)
            for part in re.split(r"→|->|,", q_stripped)
            if part.strip()
        ]
        wants_arrow = ("→" in q_stripped) or ("->" in q_stripped)

        k1 = 1.5
        b = 0.75
        scored: list[tuple[float, int, PremiseEntry]] = []

        for idx, entry in enumerate(self.entries):
            tf = self._doc_freqs[idx]
            dl = len(self._doc_tokens[idx]) or 1
            bm25 = 0.0
            for tok in q_unique:
                freq = tf.get(tok, 0)
                if freq <= 0:
                    continue
                idf = self._idf.get(tok, 0.0)
                bm25 += idf * (freq * (k1 + 1.0)) / (freq + k1 * (1.0 - b + b * dl / self._avgdl))

            # Loogle-style symbol, name, and signature structure scoring
            loogle = 0.0
            short_name = entry.name.rsplit(".", 1)[-1].lower()
            full_name_low = entry.name.lower()
            if q_lower:
                if q_lower == short_name or q_lower == full_name_low:
                    loogle += 6.0
                elif q_lower in short_name or q_lower in full_name_low:
                    loogle += 3.0
                name_parts = set(_tokenize_identifier_parts(entry.name))
                sig_tokens = _tokenize_text(entry.signature)
                sig_set = set(sig_tokens)
                for tok in q_unique:
                    if tok in name_parts:
                        loogle += 1.4
                    if tok in sig_set:
                        loogle += 0.8
                if wants_arrow and "→" in entry.signature:
                    loogle += 1.0
                if len(arrow_clauses) >= 2:
                    # Reward clauses matching in-order across the signature
                    cursor = 0
                    clause_hits = 0
                    for clause in arrow_clauses:
                        matched = False
                        for ctok in clause:
                            for pos in range(cursor, len(sig_tokens)):
                                if sig_tokens[pos] == ctok:
                                    cursor = pos + 1
                                    matched = True
                                    break
                            if matched:
                                break
                        if matched:
                            clause_hits += 1
                    loogle += 0.9 * clause_hits

            import_boost = 0.0
            if entry.module in import_set:
                import_boost = 3.5
            elif umbrella_imported and entry.module.startswith("PathWeaverFormal."):
                import_boost = 1.5
            elif any(entry.module.startswith(imp + ".") for imp in import_set):
                import_boost = 2.0

            lexical_total = bm25 + loogle
            if q_unique and lexical_total <= 0.0:
                if import_boost <= 0.0:
                    continue
                total = 0.1 * import_boost
            else:
                total = lexical_total + import_boost

            if entry.kind in {"theorem", "lemma"}:
                total += 0.05
            scored.append((total, -entry.line, entry))

        scored.sort(key=lambda item: (item[0], item[1], item[2].name), reverse=True)
        results: list[dict[str, Any]] = []
        for score, _, entry in scored[:top_k]:
            row = entry.as_dict()
            row["score"] = round(score, 4)
            results.append(row)
        return results


_INDEX_LOCK = threading.Lock()
_INDEX_CACHE: dict[str, PremiseIndex] = {}


def search_premises(
    query: str,
    *,
    imports: Sequence[str] = (),
    project_dir: str | Path | None = None,
    top_k: int = 8,
) -> list[dict[str, Any]]:
    """Query cached `PremiseIndex` for relevant Lean 4 theorems/definitions."""
    key = str(Path(project_dir).resolve()) if project_dir is not None else "__default__"
    with _INDEX_LOCK:
        index = _INDEX_CACHE.get(key)
        if index is None:
            index = PremiseIndex(project_dir)
            _INDEX_CACHE[key] = index
    return index.search(query, imports=imports, top_k=top_k)


_CURATED_OEIS: tuple[dict[str, Any], ...] = (
    {
        "id": "A003002",
        "name": "Maximum size of a 3-AP-free subset of {1..n} (Roth / Behrend / Salem-Spencer)",
        "values": (1, 2, 2, 3, 4, 4, 4, 4, 5, 5, 6, 6, 7, 8, 8, 8, 8, 8, 8, 9),
        "formula": "r_3(n): Behrend lower bound n * exp(-c * sqrt(log n))",
    },
    {
        "id": "A065825",
        "name": "Minimal length m of {1..m} admitting an n-element 3-AP-free subset",
        "values": (1, 2, 4, 5, 9, 11, 13, 14, 20),
        "formula": "min {m : r_3(m) >= n}",
    },
    {
        "id": "A005836",
        "name": "Greedy 3-AP-free (Stanley) sequence; integers with no digit 2 in base 3",
        "values": (0, 1, 3, 4, 9, 10, 12, 13, 27, 28, 30, 31, 36, 37, 39, 40),
        "formula": "sum b_i * 3^i for b_i in {0, 1}",
    },
    {
        "id": "ERDOS160_H",
        "name": "Erdos #160 (JSP-000158) exact min colors h(N) for 3-colors-per-4-AP on {1..N}",
        "values": (1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4),
        "formula": "h(N): exact 1 (N<=3), 3 (4<=N<=12), 4 (13<=N<=18); upper bounds h(77)<=7, h(98)<=8",
    },
    {
        "id": "A000108",
        "name": "Catalan numbers",
        "values": (1, 1, 2, 5, 14, 42, 132, 429, 1430, 4862, 16796, 58786, 208012, 742900),
        "formula": "C(2n, n) / (n + 1)",
    },
    {
        "id": "A000045",
        "name": "Fibonacci numbers",
        "values": (0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181),
        "formula": "F(n) = F(n - 1) + F(n - 2)",
    },
    {
        "id": "A000040",
        "name": "Prime numbers",
        "values": (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97),
        "formula": "p_n (n-th prime)",
    },
    {
        "id": "A003313",
        "name": "Length of shortest addition chain for n",
        "values": (0, 1, 2, 2, 3, 3, 4, 3, 4, 4, 5, 4, 5, 5, 5, 4, 5, 5, 6, 5),
        "formula": "l(n): minimal steps from 1 via a + b",
    },
    {
        "id": "A000791",
        "name": "Ramsey numbers R(3, n) for n >= 2",
        "values": (3, 6, 9, 14, 18, 23, 28, 36),
        "formula": "R(3, n)",
    },
    {
        "id": "A045652",
        "name": "Schur numbers S(n) (sum-free k-coloring max N) and S(n)+1",
        "values": (1, 4, 13, 44, 160),
        "formula": "S(n): max N partitionable into n sum-free subsets (A045652(n) - 1)",
    },
    {
        "id": "A000379",
        "name": "Sum-free / Ramsey Schur companion S(n) + 1 (A045652) & 2^n - 1 bounds",
        "values": (2, 5, 14, 45, 161),
        "formula": "S(n) + 1 (minimal N forcing monochromatic x + y = z)",
    },
    {
        "id": "A000079",
        "name": "Powers of 2",
        "values": (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096),
        "formula": "2^n",
    },
    {
        "id": "A000244",
        "name": "Powers of 3",
        "values": (1, 3, 9, 27, 81, 243, 729, 2187, 6561),
        "formula": "3^n",
    },
    {
        "id": "A000225",
        "name": "2^n - 1 (Mersenne / Tower of Hanoi)",
        "values": (0, 1, 3, 7, 15, 31, 63, 127, 255, 511, 1023),
        "formula": "2^n - 1",
    },
    {
        "id": "A000142",
        "name": "Factorial numbers",
        "values": (1, 1, 2, 6, 24, 120, 720, 5040, 40320, 362880),
        "formula": "n!",
    },
    {
        "id": "A000217",
        "name": "Triangular numbers",
        "values": (0, 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66, 78, 91),
        "formula": "n*(n + 1)/2",
    },
    {
        "id": "A000290",
        "name": "Square numbers",
        "values": (0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144),
        "formula": "n^2",
    },
    {
        "id": "A000578",
        "name": "Cube numbers",
        "values": (0, 1, 8, 27, 64, 125, 216, 343, 512, 729, 1000),
        "formula": "n^3",
    },
)


def _poly_mul(a: list[Fraction], b: list[Fraction]) -> list[Fraction]:
    res = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, ca in enumerate(a):
        for j, cb in enumerate(b):
            res[i + j] += ca * cb
    return res


def _format_polynomial(coeffs: list[Fraction]) -> str:
    terms: list[str] = []
    for power in range(len(coeffs) - 1, -1, -1):
        coeff = coeffs[power]
        if coeff == 0:
            continue
        if coeff.denominator == 1:
            c_str = str(coeff.numerator)
        else:
            c_str = f"({coeff.numerator}/{coeff.denominator})"
        if power == 0:
            terms.append(c_str)
        elif power == 1:
            if coeff == 1:
                terms.append("n")
            elif coeff == -1:
                terms.append("-n")
            else:
                terms.append(f"{c_str}*n")
        else:
            if coeff == 1:
                terms.append(f"n^{power}")
            elif coeff == -1:
                terms.append(f"-n^{power}")
            else:
                terms.append(f"{c_str}*n^{power}")
    if not terms:
        return "0"
    expr = terms[0]
    for term in terms[1:]:
        if term.startswith("-"):
            expr += f" - {term[1:]}"
        else:
            expr += f" + {term}"
    return expr


def _detect_polynomial_fit(seq: tuple[int, ...]) -> dict[str, Any] | None:
    """Detect exact finite-difference polynomial degree `deg <= 4` when confirmed by zero differences."""
    n = len(seq)
    if n < 2:
        return None
    diffs: list[list[int]] = [list(seq)]
    max_order = min(5, n - 1)
    for _ in range(max_order):
        prev = diffs[-1]
        diffs.append([prev[i + 1] - prev[i] for i in range(len(prev) - 1)])

    for deg in range(0, min(4, n - 2) + 1):
        next_diff = diffs[deg + 1]
        if next_diff and all(val == 0 for val in next_diff):
            # Build exact Newton forward interpolation polynomial in powers of n (0-indexed)
            coeffs = [Fraction(0)] * (deg + 1)
            falling = [Fraction(1)]
            fact = 1
            for k in range(deg + 1):
                if k > 0:
                    fact *= k
                    falling = _poly_mul(falling, [Fraction(-(k - 1)), Fraction(1)])
                weight = Fraction(diffs[k][0], fact)
                for p_idx, f_coeff in enumerate(falling):
                    coeffs[p_idx] += weight * f_coeff

            def _eval(x: int) -> Fraction:
                acc = Fraction(0)
                for p_idx, coeff in enumerate(coeffs):
                    acc += coeff * (x ** p_idx)
                return acc

            if all(_eval(i) == seq[i] for i in range(n)):
                next_terms = [int(_eval(n + offset)) for offset in range(3) if _eval(n + offset).denominator == 1]
                return {
                    "id": f"POLY_DEG_{deg}",
                    "kind": "polynomial_fit",
                    "degree": deg,
                    "name": f"Exact degree-{deg} integer polynomial (0-indexed n)",
                    "formula": _format_polynomial(coeffs),
                    "coefficients": [str(c) for c in coeffs],
                    "next_terms": next_terms,
                    "confidence": 1.0,
                }
    return None


def _detect_geometric_power(seq: tuple[int, ...]) -> dict[str, Any] | None:
    if len(seq) < 3 or seq[0] == 0:
        return None
    if seq[1] % seq[0] != 0:
        return None
    base = seq[1] // seq[0]
    if abs(base) < 2:
        return None
    scale = seq[0]
    if all(scale * (base ** idx) == val for idx, val in enumerate(seq)):
        formula = f"{base}^n" if scale == 1 else f"{scale} * {base}^n"
        next_terms = [scale * (base ** (len(seq) + k)) for k in range(3)]
        return {
            "id": "GEOMETRIC_POWER",
            "kind": "geometric_power",
            "name": f"Exact geometric sequence with ratio {base}",
            "formula": formula,
            "base": base,
            "scale": scale,
            "next_terms": next_terms,
            "confidence": 0.95,
        }
    return None


def recognize_integer_sequence(values: Sequence[int]) -> list[dict[str, Any]]:
    """Recognize exact OEIS prefix/subsequence matches, geometric powers, and degree <= 4 polynomials."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    seq = tuple(int(v) for v in values)
    if len(seq) < 2:
        return []

    matches: list[dict[str, Any]] = []
    m_len = len(seq)

    for entry in _CURATED_OEIS:
        ref = entry["values"]
        if m_len > len(ref):
            continue
        if ref[:m_len] == seq:
            matches.append({
                "id": entry["id"],
                "kind": "oeis_match",
                "match_type": "exact_prefix",
                "offset": 0,
                "name": entry["name"],
                "formula": entry["formula"],
                "next_terms": list(ref[m_len : m_len + 3]),
                "confidence": 1.0,
            })
            continue
        for start in range(1, len(ref) - m_len + 1):
            if ref[start : start + m_len] == seq:
                matches.append({
                    "id": entry["id"],
                    "kind": "oeis_match",
                    "match_type": "contiguous_subsequence",
                    "offset": start,
                    "name": entry["name"],
                    "formula": entry["formula"],
                    "next_terms": list(ref[start + m_len : start + m_len + 3]),
                    "confidence": 0.85,
                })
                break

    poly = _detect_polynomial_fit(seq)
    if poly is not None:
        matches.append(poly)

    geom = _detect_geometric_power(seq)
    if geom is not None:
        matches.append(geom)

    matches.sort(
        key=lambda item: (
            1 if item.get("match_type") == "exact_prefix" else 0,
            float(item.get("confidence", 0.0)),
        ),
        reverse=True,
    )
    return matches
