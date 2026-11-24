"""Scoped mathematical claims and evidence for serial research."""
from dataclasses import asdict, dataclass
from pathlib import Path

from pathweaver.core.contracts import canonical_json, digest, require_text
from pathweaver.core.research_records import require_id


def _ids(values):
    if not isinstance(values, list):
        raise ValueError("Claim links must be a list of IDs")
    result = [require_id(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError("Duplicate claim links")
    return result


def _text(value, field, limit=1800):
    value = require_text(value, field).strip()
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


@dataclass(frozen=True)
class Claim:
    id: str
    statement: str
    scope: str
    gap: str
    dependencies: list[str]
    related: list[str]

    @classmethod
    def parse(cls, row):
        if not isinstance(row, dict) or row.keys() != cls.__dataclass_fields__.keys():
            raise ValueError("Expected claim ID, statement, scope, gap, dependencies and related IDs")
        return cls(require_id(row["id"]), _text(row["statement"], "statement"),
                   _text(row["scope"], "scope"), _text(row["gap"], "gap"),
                   _ids(row["dependencies"]), _ids(row["related"]))


@dataclass(frozen=True)
class ClaimEvidence:
    id: str
    claim_id: str
    kind: str
    summary: str
    source: str

    @classmethod
    def parse(cls, row):
        required = set(cls.__dataclass_fields__.keys())
        if not isinstance(row, dict) or not required.issubset(row.keys()) or not set(row.keys()).issubset(required | {"sha256"}):
            raise ValueError("Expected evidence ID, claim ID, kind, summary and source")
        if row["kind"] not in ("draft", "audit", "review", "counterexample", "reference", "certificate_check", "formal_proof"):
            raise ValueError("Unknown claim evidence kind")
        return cls(require_id(row["id"]), require_id(row["claim_id"]), row["kind"],
                   _text(row["summary"], "summary"), _text(row["source"], "source"))


class ClaimLedger:
    def __init__(self):
        self.claims: dict[str, Claim] = {}
        self.evidence: dict[str, ClaimEvidence] = {}
        self.sources: dict[str, bytes] = {}

    def apply(self, bundle, root, *, model_output=False, verify_formal=False):
        """Admit a batch atomically, with premises defined before their dependents."""
        if (not isinstance(bundle, dict) or bundle.keys() != {"schema_version", "claims", "evidence"}
                or type(bundle["schema_version"]) is not int or bundle["schema_version"] != 1
                or not isinstance(bundle["claims"], list) or not isinstance(bundle["evidence"], list)):
            raise ValueError("Expected a version 1 claim bundle")
        claims, evidence = dict(self.claims), dict(self.evidence)
        sources = dict(self.sources)
        introduced = [Claim.parse(row) for row in bundle["claims"]]
        for claim in introduced:
            if claim.id in claims or any(ref not in claims for ref in claim.dependencies):
                raise ValueError(f"Duplicate claim or missing earlier dependency: {claim.id}")
            claims[claim.id] = claim
        if any(ref == claim.id or ref not in claims for claim in introduced for ref in claim.related):
            raise ValueError("Related claims must reference another known claim")
        root = Path(root).resolve()
        for row in bundle["evidence"]:
            item = ClaimEvidence.parse(row)
            if model_output and item.kind not in {"draft", "audit"}:
                raise ValueError("Model output may only supply a draft or an audit; formal/review checks require a trusted verifier")
            if item.id in evidence or item.claim_id not in claims:
                raise ValueError(f"Duplicate evidence or unknown claim: {item.id}")
            relative = Path(item.source)
            path = (root / relative).resolve()
            if relative.anchor or not path.is_relative_to(root):
                raise ValueError(f"Evidence must be relative to its bundle: {item.id}")
            with path.open("rb") as stream:
                raw = stream.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError(f"Evidence file too large: {item.id}")
            text = raw.decode("utf-8")
            if verify_formal and item.kind == "formal_proof":
                if path.suffix.lower() != ".lean":
                    raise ValueError(
                        f"Formal proof verification failed for {item.id}: expected a .lean file, got {path.name!r}"
                    )
                from pathweaver.research.formal_verifier import extract_lean_theorem_names, verify_formal_proof

                theorems = extract_lean_theorem_names(text)
                if not theorems:
                    raise ValueError(
                        f"Formal proof verification failed for {item.id}: no Lean theorem/lemma declaration found for axiom audit"
                    )
                verdict = verify_formal_proof(text, backend="lean4", theorem_name=theorems[-1])
                if verdict.status != "verified":
                    detail = "; ".join(verdict.soundness_errors) or verdict.compiler_output[:240]
                    raise ValueError(f"Formal proof verification failed for {item.id}: {verdict.status} ({detail})")
            evidence[item.id], sources[item.id] = item, raw
        self.claims, self.evidence, self.sources = claims, evidence, sources

    def dispositions(self):
        """Reviewed or formally verified premises unblock dependent claims."""
        kinds = {claim_id: set() for claim_id in self.claims}
        for item in self.evidence.values():
            kinds[item.claim_id].add(item.kind)
        states = {}
        for claim_id, claim in self.claims.items():
            evidence = kinds[claim_id]
            if "counterexample" in evidence:
                state = "refuted"
            elif any(states[ref] not in {"reviewed", "formally_verified"} for ref in claim.dependencies):
                state = "blocked"
            elif "formal_proof" in evidence:
                state = "formally_verified"
            elif "review" in evidence:
                state = "reviewed"
            elif "certificate_check" in evidence:
                state = "machine_checked"
            elif "draft" in evidence:
                state = "candidate"
            else:
                state = "open"
            states[claim_id] = state
        return states

    def _dependencies(self, claim_id):
        pending = list(self.claims[claim_id].dependencies)
        seen = set()
        while pending:
            ref = pending.pop()
            if ref not in seen:
                seen.add(ref)
                pending.extend(self.claims[ref].dependencies)
        return seen

    def _dependents_count(self):
        """Count transitive downstream claims relying on each claim for impact-weighted scheduling."""
        counts = {claim_id: 0 for claim_id in self.claims}
        for claim_id in self.claims:
            for dep in self._dependencies(claim_id):
                counts[dep] += 1
        return counts

    def impact_scores(self):
        """Return deterministic downstream dependency counts per claim."""
        return self._dependents_count()

    def plan(self, handled):
        states = self.dispositions()
        impact = self._dependents_count()
        audited = {item.claim_id for item in self.evidence.values() if item.kind in {"audit", "certificate_check"}}
        formalized = {item.claim_id for item in self.evidence.values() if item.kind == "formal_proof"}
        ordered_claims = sorted(self.claims.keys(), key=lambda cid: (-impact[cid], cid))
        for action, target_states in (
            ("audit", ("candidate",)),
            ("formalize", ("machine_checked", "reviewed", "candidate")),
            ("repair", ("blocked",)),
            ("propose", ("open",)),
        ):
            for claim_id in ordered_claims:
                disposition = states[claim_id]
                if disposition not in target_states:
                    continue
                dependencies = self._dependencies(claim_id)
                if action == "repair" and not any(states[ref] == "refuted" for ref in dependencies):
                    continue
                if action == "formalize":
                    if claim_id in formalized:
                        continue
                    # Only advance to formalization after audit/check/review, or when candidate was audited.
                    if disposition == "candidate" and claim_id not in audited:
                        continue
                related = self.claims[claim_id].related
                # Carry an open question's counterexamples into audits of drafts
                # produced for that question.
                inherited = [ref for parent in related for ref in self.claims[parent].related]
                ids = [claim_id, *sorted(dependencies), *related, *inherited]
                ids = list(dict.fromkeys(ids))
                if action == "audit" and claim_id in audited:
                    # Allow a follow-up re-audit only if new counterexample evidence exists on related/dep claims.
                    has_related_refutation = any(states[ref] == "refuted" for ref in ids if ref != claim_id)
                    if not has_related_refutation:
                        continue
                items = [item for ref in ids for item in self.evidence.values()
                         if item.claim_id == ref and (states[ref] != "refuted" or item.kind == "counterexample")]
                evidence_ids = [item.id for item in items]
                key = digest(canonical_json([action, [(ref, states[ref]) for ref in ids], evidence_ids]).encode())
                if key in handled:
                    continue
                return {
                    "action": action, "claim_id": claim_id, "work_key": key,
                    "impact_score": impact[claim_id],
                    "premise_ids": [
                        ref for ref in ids
                        if ref != claim_id and states[ref] in {"reviewed", "formally_verified"}
                    ],
                    "claims": [{**asdict(self.claims[ref]), "status": states[ref]} for ref in ids],
                    "evidence": [asdict(item) for item in items],
                }
        return None

    def extract_search_constraints(self) -> dict[str, object]:
        """Project verified barriers, conservative regime blocks, and open frontiers for search."""
        states = self.dispositions()
        impact = self.impact_scores()
        verified_barriers: list[dict[str, object]] = []
        obstructed_regimes: set[str] = set()
        open_ranked: list[tuple[int, str, dict[str, object]]] = []

        for claim_id in sorted(self.claims):
            claim = self.claims[claim_id]
            status = states[claim_id]
            combined_lower = f"{claim.statement} {claim.scope}".lower()
            if status == "refuted":
                counterexamples = [
                    item.summary for item in self.evidence.values()
                    if item.claim_id == claim_id and item.kind == "counterexample"
                ]
                verified_barriers.append({
                    "claim_id": claim_id,
                    "status": status,
                    "statement": claim.statement[:320],
                    "scope": claim.scope[:200],
                    "counterexample": counterexamples[0][:240] if counterexamples else "",
                })
                if not any(tok in claim.scope.lower() for tok in _NARROW_SCOPE_MARKERS):
                    obstructed_regimes.update(_infer_claim_regimes(combined_lower))
            elif status in {"formally_verified", "reviewed", "machine_checked"} and any(
                marker in combined_lower for marker in _BARRIER_MARKERS
            ):
                verified_barriers.append({
                    "claim_id": claim_id,
                    "status": status,
                    "statement": claim.statement[:320],
                    "scope": claim.scope[:200],
                })
            elif status in {"open", "candidate"}:
                open_ranked.append((
                    -impact[claim_id],
                    claim_id,
                    {
                        "claim_id": claim_id,
                        "status": status,
                        "impact_score": impact[claim_id],
                        "statement": claim.statement[:320],
                        "scope": claim.scope[:200],
                        "gap": claim.gap[:200],
                    },
                ))

        verified_barriers.sort(key=lambda row: (-impact.get(str(row["claim_id"]), 0), str(row["claim_id"])))
        open_ranked.sort(key=lambda item: (item[0], item[1]))
        return {
            "obstructed_regimes": sorted(obstructed_regimes),
            "verified_barriers": verified_barriers[:8],
            "open_high_impact_claims": [item[2] for item in open_ranked[:5]],
        }


_BARRIER_MARKERS = (
    "obstruction", "excluded", "cannot", "impossible", "nonexistence",
    "contradiction", "lower bound", "obstructed", "fails", "no ",
)
_NARROW_SCOPE_MARKERS = (
    "only ", "restricted", "fixed ", "modulo ", "p =", "q =", "m <", "n <=", "single ",
)
_CLAIM_REGIME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("algebraic_modular_group", ("cyclic", "frobenius", "coset", "modular", "quotient", "finite field", "finite-field", "power map", "biquintic", "quintic", "fourier", "moment kernel", "stabilizer")),
    ("greedy_local_search", ("greedy", "local search", "1-swap", "single-point", "recolor")),
    ("bipartite_matching_flow", ("hungarian", "bipartite", "matching", "hall", "min-cost flow", "augmenting")),
    ("spectral_relaxation_rounding", ("lagrangian", "subgradient", "spectral", "laplacian", "lp relaxation", "dual packing")),
    ("exact_branch_and_reduce", ("branch-and-bound", "branch and bound", "backtracking", "kernelization", "dsatur")),
)


def _infer_claim_regimes(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    matched = [regime for regime, kws in _CLAIM_REGIME_KEYWORDS if any(kw in lowered for kw in kws)]
    return tuple(matched)


def build_empirical_conjecture_bundle(
    *,
    claim_id: str,
    statement: str,
    scope: str,
    gap: str,
    summary: str,
    evidence_rel_path: str,
) -> dict[str, object]:
    """Build a version-1 ClaimLedger bundle containing a single empirical draft conjecture."""
    cid = require_id(claim_id)
    return {
        "schema_version": 1,
        "claims": [
            {
                "id": cid,
                "statement": _text(statement, "statement"),
                "scope": _text(scope, "scope"),
                "gap": _text(gap, "gap"),
                "dependencies": [],
                "related": [],
            }
        ],
        "evidence": [
            {
                "id": f"{cid}-draft",
                "claim_id": cid,
                "kind": "draft",
                "summary": _text(summary, "summary"),
                "source": _text(evidence_rel_path, "source"),
            }
        ],
    }
