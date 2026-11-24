"""Deterministic structural + UCB-attributed slot retrieval with temporal visibility."""
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
    bottleneck_instances: tuple[str, ...] = ()
    current_regime: str = ""
    slot_mode: bool = True


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


def _is_execution_noise(event: ResearchEvent) -> bool:
    tags = event.payload.get("tags") or ()
    if "signal:execution_noise" in tags:
        return True
    return event.kind == "attempt" and event.payload.get("outcome") in {"malformed", "timeout", "exception"}


def _attribution_stats(records: list[ResearchEvent], run_id: str) -> tuple[Counter[str], Counter[str], Counter[str]]:
    exposure_counts: Counter[str] = Counter()
    win_counts: Counter[str] = Counter()
    regression_counts: Counter[str] = Counter()
    for event in records:
        if event.kind != "attempt" or event.run_id != run_id:
            continue
        delta = (event.payload.get("diagnostics") or {}).get("delta") or {}
        signal_tier = delta.get("signal_tier") or ""
        improved = signal_tier in {"breakthrough", "stepping_stone"}
        regressed = bool(delta.get("regressed_instances")) and not improved
        exposed = set(event.context_exposures)
        if event.payload.get("hypothesis_id"):
            exposed.add(str(event.payload["hypothesis_id"]))
        declared_lesson = delta.get("declared_lesson_id")
        if isinstance(declared_lesson, str) and declared_lesson:
            exposed.add(declared_lesson)
        for ref_id in exposed:
            exposure_counts[ref_id] += 1
            if improved:
                win_counts[ref_id] += 1
            elif regressed:
                regression_counts[ref_id] += 1
    return exposure_counts, win_counts, regression_counts


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
    exposure_counts, win_counts, regression_counts = _attribution_stats(records, query.run_id)
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
        elif (
            query.transfer_advice
            and event.kind == "lesson"
            and event.payload["state"] == "experimental"
            and source_scope["task_id"] != run.payload["scope"]["task_id"]
            and set(query.tags).intersection(event.payload.get("tags", []))
        ):
            candidates.append((event, True, status, info))

    texts = [Counter(_tokens(canonical_json(e.payload))) for e, _, _, _ in candidates]
    document_frequency = Counter(token for doc in texts for token in doc)
    average_length = sum(sum(doc.values()) for doc in texts) / max(1, len(texts)) or 1
    query_tokens = set(_tokens(query.text))
    query_tag_set = set(query.tags)
    bottlenecks = tuple(query.bottleneck_instances)
    hits: list[MemoryHit] = []
    status_multiplier = {"active": 1.0, "degraded": 0.6, "context_tainted": 0.35}

    for (event, advice, status, info), doc in zip(candidates, texts):
        score = 0.0
        for token in query_tokens:
            frequency = doc[token]
            if frequency:
                idf = math.log(1 + (len(texts) - document_frequency[token] + .5) / (document_frequency[token] + .5))
                score += idf * frequency * 2.2 / (frequency + 1.2 * (.25 + .75 * sum(doc.values()) / average_length))

        tags = set(event.payload.get("tags", []))
        score += 2.0 * len(query_tag_set.intersection(tags))

        # Signal-tier differentiation: reward breakthroughs/stepping-stones, suppress execution noise.
        if "signal:breakthrough" in tags:
            score += 1.6
        elif "signal:stepping_stone" in tags:
            score += 1.4
        elif "signal:structural_obstruction" in tags:
            score += 0.7
        elif _is_execution_noise(event):
            score -= 2.0
        elif event.kind == "attempt" and event.payload["outcome"] == "invalid":
            score += 0.6

        # Structural bottleneck and regime alignment.
        for inst_id in bottlenecks:
            if f"win_inst:{inst_id}" in tags or f"stepping_stone_on:{inst_id}" in tags:
                score += 3.0
            elif f"bottleneck_inst:{inst_id}" in tags and event.kind in {"lesson", "hypothesis", "route"}:
                score += 2.0

        if query.current_regime and f"regime:{query.current_regime}" in tags:
            if (
                event.kind in {"lesson", "hypothesis"}
                and (event.payload.get("contradiction_ids") or event.payload.get("state") == "refuted")
            ) or event.kind == "route":
                score += 1.8
            else:
                score += 0.4

        # Empirical UCB attribution utility and sterile exposure decay.
        exp_n = exposure_counts[event.record_id]
        win_n = win_counts[event.record_id]
        reg_n = regression_counts[event.record_id]
        if win_n > 0:
            score += 1.8 * (win_n / (exp_n + 1.0))
        elif exp_n >= 4:
            if score > 0:
                score *= 1.0 / (1.0 + 0.25 * (exp_n - 3) + 0.2 * reg_n)
            else:
                score -= 0.2 * (exp_n - 3) + 0.2 * reg_n

        mult = status_multiplier.get(status, 0.5)
        if score > 0:
            score *= mult
        elif mult < 1.0:
            score -= (1.0 - mult)
        hits.append(MemoryHit(event, score, advice, integrity_status=status, integrity_detail=info))

    # Score match first, newest evidence as deterministic tie-breaker.
    hits.sort(key=lambda h: (-h.score, -h.event.sequence, h.event.record_id))
    has_non_noise_attempt = any(h.event.kind == "attempt" and not _is_execution_noise(h.event) for h in hits)
    pool = [
        h for h in hits
        if not (has_non_noise_attempt and h.event.kind == "attempt" and _is_execution_noise(h.event))
    ]

    counts: Counter[str] = Counter()
    selected: list[MemoryHit] = []
    selected_ids: set[str] = set()

    def _try_add(hit: MemoryHit) -> bool:
        if hit.event.record_id in selected_ids:
            return False
        if counts[hit.event.kind] >= query.per_kind:
            return False
        selected.append(hit)
        selected_ids.add(hit.event.record_id)
        counts[hit.event.kind] += 1
        return True

    if query.slot_mode:
        # Slot 1: Bottleneck solvers & positive breakthroughs (up to 2).
        s1 = 0
        for hit in pool:
            if s1 >= 2:
                break
            tags = set(hit.event.payload.get("tags", []))
            matches_bottleneck = any(
                f"win_inst:{iid}" in tags or f"stepping_stone_on:{iid}" in tags
                for iid in bottlenecks
            )
            if matches_bottleneck or "signal:breakthrough" in tags or "signal:stepping_stone" in tags:
                if _try_add(hit):
                    s1 += 1

        # Slot 2: Same-regime obstructions / anti-patterns (up to 2).
        s2 = 0
        for hit in pool:
            if s2 >= 2:
                break
            tags = set(hit.event.payload.get("tags", []))
            same_regime = bool(query.current_regime) and f"regime:{query.current_regime}" in tags
            is_obstruction = (
                "signal:structural_obstruction" in tags
                or bool(hit.event.payload.get("contradiction_ids"))
                or hit.event.payload.get("state") == "refuted"
            )
            if (same_regime and is_obstruction) or (not query.current_regime and is_obstruction):
                if _try_add(hit):
                    s2 += 1

        # Slot 3: Active exploration agenda (routes / open hypotheses / experimental lessons).
        for hit in pool:
            kind = hit.event.kind
            state = hit.event.payload.get("state")
            if (kind == "route" and state in {"active", "queued"}) or (
                kind == "hypothesis" and state == "open"
            ) or (kind == "lesson" and state == "experimental"):
                _try_add(hit)

    # Fill any remaining per_kind capacity deterministically by rank.
    for hit in pool:
        _try_add(hit)
    return selected
