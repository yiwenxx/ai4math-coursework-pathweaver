"""Deterministic lexical retrieval with run, version and temporal visibility."""
from collections import Counter
from dataclasses import dataclass
import math
import re

from pathweaver.core.research_records import ResearchEvent, canonical_json
from pathweaver.research.memory.store import MemoryStore


@dataclass(frozen=True)
class MemoryQuery:
    run_id: str
    text: str = ""
    tags: tuple[str, ...] = ()
    as_of: int | None = None
    include_runs: tuple[str, ...] = ()
    transfer_advice: bool = False
    per_kind: int = 3
    include_degraded: bool = True
    include_tainted: bool = False


@dataclass(frozen=True)
class MemoryHit:
    event: ResearchEvent
    score: float
    advice_only: bool
    integrity_status: str = "active"
    integrity_detail: dict[str, object] | None = None


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    tokens: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u4e00-\u9fff]+", word):
            tokens.extend(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        else:
            tokens.append(word)
    return tokens


def retrieve(store: MemoryStore, query: MemoryQuery) -> list[MemoryHit]:
    if query.per_kind < 1:
        raise ValueError("per_kind must be positive")
    cutoff = store.sequence if query.as_of is None else query.as_of
    if type(cutoff) is not int or not 0 <= cutoff <= store.sequence:
        raise ValueError("as_of must be an existing, nonnegative ledger sequence")
    run = store.get(query.run_id, as_of=cutoff)
    if run.kind != "run":
        raise ValueError("Memory queries must identify a run")
    details = store.integrity_details(as_of=cutoff)
    if details.get(run.record_id, {}).get("status") != "active":
        raise ValueError("Cannot use memory from an invalidated run")
    records = store.snapshot(as_of=cutoff)
    runs = {e.record_id: e for e in records if e.kind == "run"}
    candidates: list[tuple[ResearchEvent, bool, str, dict[str, object]]] = []

    allowed_statuses = {"active"}
    if query.include_degraded:
        allowed_statuses.add("degraded")
    if query.include_tainted:
        allowed_statuses.add("context_tainted")

    def eligible(event: ResearchEvent) -> tuple[bool, str, dict[str, object]]:
        info = details.get(event.record_id, {"status": "revoked"})
        status = info["status"]
        if event.kind not in {"attempt", "hypothesis", "lesson", "route"} or status not in allowed_statuses:
            return False, status, info
        if event.kind == "lesson" and event.payload["state"] == "retired":
            return False, status, info
        if event.kind == "route" and event.payload["state"] in {"done", "paused"}:
            return False, status, info
        return True, status, info

    for event in records:
        ok, status, info = eligible(event)
        if not ok:
            continue
        if event.run_id == query.run_id:
            candidates.append((event, False, status, info))
            continue
        source_run = runs.get(event.run_id)
        if source_run is None or source_run.payload["provenance"] == "illustrative":
            continue
        source_scope = source_run.payload["scope"]
        same_scope = source_scope == run.payload["scope"]
        if event.run_id in query.include_runs and same_scope:
            candidates.append((event, False, status, info))
        elif (query.transfer_advice and event.kind == "lesson"
              and event.payload["state"] == "experimental"
              and source_scope["task_id"] != run.payload["scope"]["task_id"]
              and set(query.tags).intersection(event.payload.get("tags", []))):
            candidates.append((event, True, status, info))

    texts = [Counter(_tokens(canonical_json(e.payload))) for e, _, _, _ in candidates]
    document_frequency = Counter(token for doc in texts for token in doc)
    average_length = sum(sum(doc.values()) for doc in texts) / max(1, len(texts)) or 1
    query_tokens = set(_tokens(query.text))
    hits: list[MemoryHit] = []
    status_multiplier = {"active": 1.0, "degraded": 0.6, "context_tainted": 0.35}
    for (event, advice, status, info), doc in zip(candidates, texts):
        score = 0.0
        for token in query_tokens:
            frequency = doc[token]
            if frequency:
                idf = math.log(1 + (len(texts) - document_frequency[token] + .5) / (document_frequency[token] + .5))
                score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * sum(doc.values()) / average_length))
        score += 2 * len(set(query.tags).intersection(event.payload.get("tags", [])))
        if event.kind == "attempt" and event.payload["outcome"] != "feasible":
            score += .5
        score *= status_multiplier.get(status, 0.5)
        hits.append(MemoryHit(event, score, advice, integrity_status=status, integrity_detail=info))
    # Lexical match first, newest evidence as a deterministic tie-breaker.
    hits.sort(key=lambda h: (-h.score, -h.event.sequence, h.event.record_id))
    counts: Counter[str] = Counter()
    selected: list[MemoryHit] = []
    for hit in hits:
        if counts[hit.event.kind] < query.per_kind:
            selected.append(hit)
            counts[hit.event.kind] += 1
    return selected
