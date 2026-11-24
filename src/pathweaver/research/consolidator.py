"""Dual-speed event-triggered memory consolidation with anti-hallucination gating."""
from collections.abc import Mapping, Sequence
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from pathweaver.core.research_records import ResearchEvent, canonical_json
from pathweaver.research.memory.retrieval import _attribution_stats
from pathweaver.research.memory.store import MemoryStore

try:
    from pathweaver.research.discovery_config import is_local_endpoint
except ImportError:
    def is_local_endpoint(endpoint: str) -> bool:
        url = urlsplit(endpoint)
        return url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}

try:
    from pathweaver.research.run_state import StopRun, currency_units
except ImportError:
    class StopRun(BaseException):
        pass

    def currency_units(value: object) -> int:
        return int((Decimal(str(value)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


CONSOLIDATOR_SYSTEM_PROMPT = (
    "You are PathWeaver's epistemic research memory consolidator.\n"
    "Analyze the incremental verified training attempts since the last checkpoint and output ONLY a valid JSON object:\n"
    "{\n"
    '  "lessons": [{"record_id": optional_existing_id, "statement": str, "conditions": str, '
    '"state": "provisional"|"experimental"|"retired", "support_ids": [attempt_id], '
    '"contradiction_ids": [attempt_id], "tags": [str]}],\n'
    '  "hypotheses": [{"record_id": optional_existing_id, "statement": str, "test_plan": str, '
    '"state": "open"|"supported"|"refuted"|"inconclusive", "support_ids": [attempt_id], '
    '"contradiction_ids": [attempt_id], "tags": [str]}],\n'
    '  "routes": [{"record_id": optional_existing_id, "action": "variant"|"diagnose"|"controlled_compare"|"scale"|"restart", '
    '"rationale": str, "state": "queued"|"active"|"done"|"paused", "hypothesis_id": optional_id, '
    '"evidence_ids": [attempt_id], "tags": [str]}],\n'
    '  "obstructed_regimes": [str]\n'
    "}\n"
    "Rules:\n"
    "1. Cite ONLY exact attempt IDs visible in the evidence digest. Never invent IDs.\n"
    "2. Keep each list to at most 2 concise, falsifiable entries grounded in observed deltas and diagnostics.\n"
    "3. Output an obstructed_regimes entry only when backed by a refuted hypothesis or contradiction evidence."
)

_KNOWN_REGIMES = frozenset({
    "greedy_local_search",
    "bipartite_matching_flow",
    "spectral_relaxation_rounding",
    "exact_branch_and_reduce",
    "algebraic_modular_group",
    "metaheuristic_population",
    "general_constructive",
    "induction_case_analysis",
    "algebraic_rewriting_automation",
    "structured_lemma_decomposition",
    "tactic_automation",
})


def _extract_json_object(text: str) -> dict[str, Any] | None:
    if not isinstance(text, str) or not text.strip():
        return None
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    candidates = [fence.group(1)] if fence else []
    candidates.append(stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start:end + 1])
    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _clean_tags(raw_tags: Any, fallback: str) -> list[str]:
    tags = [str(t).strip() for t in (raw_tags or ()) if isinstance(t, str) and t.strip()]
    if not tags:
        tags = [fallback]
    return list(dict.fromkeys(tags))[:8]


class MemoryConsolidator:
    """Event-triggered memory curation and budgeted LLM consolidation."""

    def __init__(
        self,
        database_path: str | Path,
        run_id: str,
        *,
        gateway: Any = None,
        state: Any = None,
        interval: int = 4,
        use_llm: bool = True,
    ):
        self.database_path = Path(database_path)
        self.run_id = run_id
        self.gateway = gateway
        self.state = state
        self.interval = max(1, int(interval))
        self.use_llm = use_llm

    @staticmethod
    def _last_checkpoint_cutoff(records: Sequence[ResearchEvent], details: Mapping[str, Mapping[str, Any]]) -> int:
        cutoffs = [
            int(e.payload.get("through_sequence", 0))
            for e in records
            if e.kind == "checkpoint" and details.get(e.record_id, {}).get("status") not in {"revoked", "needs_review"}
        ]
        return max(cutoffs, default=0)

    def should_consolidate(self, *, stagnation_monitor: Any = None) -> tuple[bool, str]:
        with MemoryStore(self.database_path, readonly=True) as store:
            records = store.snapshot(run_id=self.run_id)
            details = store.integrity_details(records=records)
        last_cutoff = self._last_checkpoint_cutoff(records, details)
        new_attempts = [
            e for e in records
            if e.kind == "attempt"
            and e.sequence > last_cutoff
            and details.get(e.record_id, {}).get("status") not in {"revoked", "needs_review"}
        ]
        if not new_attempts:
            return False, ""
        for attempt in new_attempts:
            tags = set(attempt.payload.get("tags") or ())
            if "signal:breakthrough" in tags or "signal:stepping_stone" in tags:
                return True, "breakthrough_or_stepping_stone"
        for attempt in new_attempts:
            if attempt.payload.get("verification") == "verified" and attempt.payload.get("hypothesis_id"):
                return True, "hypothesis_evidence"
        if (
            stagnation_monitor is not None
            and stagnation_monitor.no_improve_streak >= stagnation_monitor.stagnation_window
            and len(new_attempts) >= 2
        ):
            return True, "stagnation_trap"
        if len(new_attempts) >= self.interval:
            return True, "periodic_interval"
        return False, ""

    def deterministic_curate(
        self,
        store: MemoryStore,
        *,
        last_cutoff: int | None = None,
    ) -> dict[str, Any]:
        """Run zero-cost epistemic curation, hypothesis adjudication, and stepping-stone crystallization."""
        records = store.snapshot(run_id=self.run_id)
        details = store.integrity_details(records=records)
        if last_cutoff is None:
            last_cutoff = self._last_checkpoint_cutoff(records, details)

        run_event = store.get(self.run_id)
        scope = run_event.payload["scope"]
        exposure_counts, win_counts, regression_counts = _attribution_stats(records, self.run_id)
        by_id = {e.record_id: e for e in records}
        valid_exposure_ids = {
            e.record_id for e in records if e.kind in {"attempt", "hypothesis", "lesson", "route"}
        }

        retired_lessons: list[str] = []
        contradicted_lessons: list[str] = []
        adjudicated_hypotheses: list[str] = []
        crystallized_lessons: list[str] = []

        # 1. Auto-retire sterile provisional lessons that saw repeated exposure with zero wins and regressions.
        for event in records:
            if (
                event.kind == "lesson"
                and event.payload.get("state") == "provisional"
                and details.get(event.record_id, {}).get("status") == "active"
            ):
                exp_n = exposure_counts[event.record_id]
                win_n = win_counts[event.record_id]
                reg_n = regression_counts[event.record_id]
                if exp_n >= 5 and win_n == 0 and reg_n >= 2:
                    updated = dict(event.payload)
                    updated["state"] = "retired"
                    store.append(
                        "lesson",
                        self.run_id,
                        updated,
                        record_id=event.record_id,
                        expected_revision=event.revision,
                    )
                    retired_lessons.append(event.record_id)

        # Refresh snapshot after retirements.
        records = store.snapshot(run_id=self.run_id)
        details = store.integrity_details(records=records)
        by_id = {e.record_id: e for e in records}

        verified_active_attempts = [
            e for e in records
            if e.kind == "attempt"
            and e.payload.get("verification") == "verified"
            and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        ]
        verified_active_ids = {e.record_id for e in verified_active_attempts}

        # 2. Link contradicting verified attempts back onto declared lessons.
        for att in verified_active_attempts:
            if att.sequence <= last_cutoff:
                continue
            delta = (att.payload.get("diagnostics") or {}).get("delta") or {}
            lesson_id = delta.get("declared_lesson_id")
            if not isinstance(lesson_id, str) or lesson_id not in by_id:
                continue
            lesson = by_id[lesson_id]
            if lesson.kind != "lesson" or details.get(lesson_id, {}).get("status") not in {"active", "degraded"}:
                continue
            tier = delta.get("signal_tier")
            is_negative = (
                att.payload.get("outcome") == "invalid"
                or (bool(delta.get("regressed_instances")) and tier not in {"breakthrough", "stepping_stone"})
            )
            if not is_negative:
                continue
            existing_cons = list(lesson.payload.get("contradiction_ids") or ())
            if att.record_id not in existing_cons:
                updated = dict(lesson.payload)
                updated["contradiction_ids"] = [*existing_cons, att.record_id]
                rev_ev = store.append(
                    "lesson",
                    self.run_id,
                    updated,
                    record_id=lesson.record_id,
                    expected_revision=lesson.revision,
                )
                by_id[lesson_id] = rev_ev
                contradicted_lessons.append(lesson_id)

        # 3. Auto-adjudicate open hypotheses based on linked verified attempts.
        for hyp in list(by_id.values()):
            if (
                hyp.kind != "hypothesis"
                or hyp.payload.get("state") != "open"
                or details.get(hyp.record_id, {}).get("status") not in {"active", "degraded"}
            ):
                continue
            linked = [
                att for att in verified_active_attempts
                if att.payload.get("hypothesis_id") == hyp.record_id
            ]
            if not linked:
                continue
            pos_new: list[str] = []
            neg_new: list[str] = []
            for att in linked:
                delta = (att.payload.get("diagnostics") or {}).get("delta") or {}
                tier = delta.get("signal_tier")
                if tier in {"breakthrough", "stepping_stone"}:
                    pos_new.append(att.record_id)
                elif att.payload.get("outcome") == "invalid" or bool(delta.get("regressed_instances")):
                    neg_new.append(att.record_id)
            all_pos = list(dict.fromkeys([*(hyp.payload.get("support_ids") or ()), *pos_new]))
            all_neg = list(dict.fromkeys([*(hyp.payload.get("contradiction_ids") or ()), *neg_new]))
            if not pos_new and not neg_new:
                continue
            new_state = "open"
            if all_pos and not all_neg and all(sid in verified_active_ids for sid in all_pos):
                new_state = "supported"
            elif len(all_neg) >= 2 and not all_pos and all(cid in verified_active_ids for cid in all_neg):
                new_state = "refuted"
            updated = dict(hyp.payload)
            updated["support_ids"] = all_pos
            updated["contradiction_ids"] = all_neg
            updated["state"] = new_state
            store.append(
                "hypothesis",
                self.run_id,
                updated,
                record_id=hyp.record_id,
                expected_revision=hyp.revision,
            )
            adjudicated_hypotheses.append(hyp.record_id)

        # 4. Auto-crystallize verified breakthroughs and stepping stones into experimental lessons.
        already_supported = {
            sid
            for e in store.snapshot(run_id=self.run_id)
            if e.kind == "lesson" and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
            for sid in (e.payload.get("support_ids") or ())
        }
        for att in verified_active_attempts:
            if att.sequence <= last_cutoff or att.record_id in already_supported:
                continue
            delta = (att.payload.get("diagnostics") or {}).get("delta") or {}
            tier = delta.get("signal_tier")
            if tier not in {"breakthrough", "stepping_stone"}:
                continue
            regime = delta.get("regime", "general_constructive")
            transition = delta.get("regime_transition", regime)
            wins = list(delta.get("improved_instances") or ())[:4]
            bottlenecks = list(delta.get("bottleneck_instances") or ())[:3]
            if tier == "breakthrough":
                stmt = (
                    f"Algorithmic transition {transition} achieved objective delta {delta.get('objective_delta')} "
                    f"(bound_gap_delta={delta.get('bound_gap_delta')})."
                )
            else:
                stmt = f"Stepping-stone transition {transition} improved instance subset {wins}."
            cond = (
                f"task={scope['task_id']}; regime={regime}; "
                f"improved_instances={wins}; remaining_bottlenecks={bottlenecks}"
            )
            tags = [
                t for t in (att.payload.get("tags") or ())
                if t.startswith(("regime:", "win_inst:", "stepping_stone_on:", "bottleneck_inst:"))
            ]
            if not tags:
                tags = [f"regime:{regime}"]
            payload: dict[str, Any] = {
                "statement": stmt,
                "conditions": cond,
                "state": "experimental",
                "support_ids": [att.record_id],
                "contradiction_ids": [],
                "tags": list(dict.fromkeys(tags)),
            }
            exposures = [eid for eid in att.context_exposures if eid in valid_exposure_ids]
            if exposures:
                payload["context_exposure_ids"] = exposures
            lesson_ev = store.append("lesson", self.run_id, payload)
            crystallized_lessons.append(lesson_ev.record_id)
            already_supported.add(att.record_id)

        return {
            "last_cutoff": last_cutoff,
            "retired_lessons": retired_lessons,
            "contradicted_lessons": contradicted_lessons,
            "adjudicated_hypotheses": adjudicated_hypotheses,
            "crystallized_lessons": crystallized_lessons,
        }

    def _has_llm_budget(self) -> bool:
        if not self.use_llm or self.gateway is None or self.state is None:
            return False
        try:
            if self.state.remaining() <= 5.0:
                return False
        except StopRun:
            return False
        calls_used = len(self.state.data.get("calls") or {})
        if calls_used + 1 >= self.state.config.budget.max_model_calls:
            return False
        llm = self.state.config.llm
        if llm.backend == "api" and not is_local_endpoint(llm.endpoint):
            reserve = self.state.token_cost(llm.input_token_ceiling, llm.max_completion_tokens)
            max_cost = currency_units(self.state.config.budget.max_api_cost)
            if self.state.data.get("charged_micro", 0) + reserve > max_cost:
                return False
        return True

    def _build_digest_prompt(
        self,
        records: Sequence[ResearchEvent],
        details: Mapping[str, Mapping[str, Any]],
        last_cutoff: int,
        stagnation_monitor: Any,
        claim_constraints: Mapping[str, Any] | None,
    ) -> tuple[str, list[str]]:
        exposed_ids: list[str] = []
        new_attempts = [
            e for e in records
            if e.kind == "attempt"
            and e.sequence > last_cutoff
            and details.get(e.record_id, {}).get("status") not in {"revoked", "needs_review"}
        ][-8:]
        active_knowledge = [
            e for e in records
            if e.kind in {"lesson", "hypothesis", "route"}
            and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        ][-8:]

        attempt_rows = []
        for att in new_attempts:
            exposed_ids.append(att.record_id)
            diag = att.payload.get("diagnostics") or {}
            delta = diag.get("delta") if isinstance(diag, dict) else {}
            attempt_rows.append({
                "id": att.record_id,
                "outcome": att.payload.get("outcome"),
                "verification": att.payload.get("verification"),
                "role": att.payload.get("dataset_role", "fitness"),
                "objectives": att.payload.get("objectives"),
                "hypothesis_id": att.payload.get("hypothesis_id"),
                "delta": {
                    k: delta.get(k)
                    for k in (
                        "regime_transition", "signal_tier", "objective_delta",
                        "total_bound_gap", "bound_gap_delta", "improved_instances",
                        "regressed_instances", "bottleneck_instances",
                    )
                    if isinstance(delta, dict) and delta.get(k) is not None
                },
                "failure": str(diag.get("failure", ""))[:220],
            })

        knowledge_rows = []
        for item in active_knowledge:
            exposed_ids.append(item.record_id)
            row: dict[str, Any] = {
                "id": item.record_id,
                "kind": item.kind,
                "revision": item.revision,
                "state": item.payload.get("state"),
            }
            for key in ("statement", "conditions", "test_plan", "action", "rationale"):
                if key in item.payload:
                    row[key] = str(item.payload[key])[:200]
            knowledge_rows.append(row)

        digest_doc: dict[str, Any] = {
            "run_id": self.run_id,
            "last_checkpoint_cutoff": last_cutoff,
            "new_attempts": attempt_rows,
            "active_memory": knowledge_rows,
        }
        if stagnation_monitor is not None:
            digest_doc["stagnation"] = {
                "no_improve_streak": stagnation_monitor.no_improve_streak,
                "empirical_obstructed_regimes": dict(stagnation_monitor.empirical_obstructed_regimes),
            }
        if claim_constraints:
            digest_doc["verified_barriers"] = list(claim_constraints.get("verified_barriers") or ())[:4]

        text = canonical_json(digest_doc)
        if len(text) > 5800:
            text = text[:5800]
        return text, list(dict.fromkeys(exposed_ids))

    def _admit_llm_bundle(
        self,
        store: MemoryStore,
        bundle: Mapping[str, Any],
        prompt_exposed_ids: Sequence[str],
    ) -> dict[str, Any]:
        records = store.snapshot(run_id=self.run_id)
        details = store.integrity_details(records=records)
        by_id = {e.record_id: e for e in records}
        valid_attempt_ids = {
            e.record_id for e in records
            if e.kind == "attempt" and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        }
        verified_active_attempt_ids = {
            e.record_id for e in records
            if e.kind == "attempt"
            and e.payload.get("verification") == "verified"
            and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        }
        valid_hyp_ids = {
            e.record_id for e in records
            if e.kind == "hypothesis" and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        }
        valid_exposure_ids = {
            e.record_id for e in records
            if e.kind in {"attempt", "hypothesis", "lesson", "route"}
        }
        exposure_refs = [eid for eid in prompt_exposed_ids if eid in valid_exposure_ids]

        admitted = {"lessons": [], "hypotheses": [], "routes": [], "obstructed_regimes": []}
        has_refutation_or_contradiction = False

        # Admit at most 2 hypotheses first so routes can reference them.
        for row in (bundle.get("hypotheses") or [])[:2]:
            if not isinstance(row, Mapping):
                continue
            statement = str(row.get("statement") or "").strip()[:1200]
            test_plan = str(row.get("test_plan") or "").strip()[:1200]
            if not statement or not test_plan:
                continue
            sup_ids = [sid for sid in (row.get("support_ids") or ()) if isinstance(sid, str) and sid in valid_attempt_ids]
            con_ids = [cid for cid in (row.get("contradiction_ids") or ()) if isinstance(cid, str) and cid in valid_attempt_ids]
            state = str(row.get("state") or "open")
            if state not in {"open", "supported", "refuted", "inconclusive"}:
                state = "open"
            if state == "supported" and (not sup_ids or not all(sid in verified_active_attempt_ids for sid in sup_ids)):
                state = "open"
            if state == "refuted" and (not con_ids or not all(cid in verified_active_attempt_ids for cid in con_ids)):
                state = "open"
            if state == "refuted" or con_ids:
                has_refutation_or_contradiction = True

            rec_id = row.get("record_id")
            expected_rev = None
            target_id = None
            if (
                isinstance(rec_id, str)
                and rec_id in by_id
                and by_id[rec_id].kind == "hypothesis"
                and details.get(rec_id, {}).get("status") in {"active", "degraded"}
            ):
                target_id = rec_id
                expected_rev = by_id[rec_id].revision
            payload: dict[str, Any] = {
                "statement": statement,
                "test_plan": test_plan,
                "state": state,
                "support_ids": list(dict.fromkeys(sup_ids)),
                "contradiction_ids": list(dict.fromkeys(con_ids)),
                "tags": _clean_tags(row.get("tags"), "consolidator_hypothesis"),
            }
            if exposure_refs:
                payload["context_exposure_ids"] = exposure_refs
            ev = store.append("hypothesis", self.run_id, payload, record_id=target_id, expected_revision=expected_rev)
            valid_hyp_ids.add(ev.record_id)
            by_id[ev.record_id] = ev
            admitted["hypotheses"].append(ev.record_id)

        # Admit at most 2 lessons.
        for row in (bundle.get("lessons") or [])[:2]:
            if not isinstance(row, Mapping):
                continue
            statement = str(row.get("statement") or "").strip()[:1200]
            conditions = str(row.get("conditions") or "").strip()[:1200]
            if not statement or not conditions:
                continue
            rec_id = row.get("record_id")
            expected_rev = None
            target_id = None
            existing_sup: list[str] = []
            if (
                isinstance(rec_id, str)
                and rec_id in by_id
                and by_id[rec_id].kind == "lesson"
                and details.get(rec_id, {}).get("status") in {"active", "degraded"}
            ):
                target_id = rec_id
                expected_rev = by_id[rec_id].revision
                existing_sup = list(by_id[rec_id].payload.get("support_ids") or ())

            sup_ids = [sid for sid in (row.get("support_ids") or ()) if isinstance(sid, str) and sid in valid_attempt_ids]
            if not sup_ids:
                sup_ids = [sid for sid in existing_sup if sid in valid_attempt_ids]
            if not sup_ids:
                continue
            con_ids = [cid for cid in (row.get("contradiction_ids") or ()) if isinstance(cid, str) and cid in valid_attempt_ids]
            if con_ids:
                has_refutation_or_contradiction = True
            state = str(row.get("state") or "provisional")
            if state not in {"provisional", "experimental", "retired"}:
                state = "provisional"
            if state == "experimental" and not all(sid in verified_active_attempt_ids for sid in sup_ids):
                state = "provisional"

            payload = {
                "statement": statement,
                "conditions": conditions,
                "state": state,
                "support_ids": list(dict.fromkeys(sup_ids)),
                "contradiction_ids": list(dict.fromkeys(con_ids)),
                "tags": _clean_tags(row.get("tags"), "consolidator_lesson"),
            }
            if exposure_refs:
                payload["context_exposure_ids"] = exposure_refs
            ev = store.append("lesson", self.run_id, payload, record_id=target_id, expected_revision=expected_rev)
            by_id[ev.record_id] = ev
            admitted["lessons"].append(ev.record_id)

        # Admit at most 2 routes.
        for row in (bundle.get("routes") or [])[:2]:
            if not isinstance(row, Mapping):
                continue
            rationale = str(row.get("rationale") or "").strip()[:1200]
            action = str(row.get("action") or "variant")
            state = str(row.get("state") or "queued")
            if not rationale:
                continue
            if action not in {"variant", "diagnose", "controlled_compare", "scale", "restart"}:
                action = "variant"
            if state not in {"queued", "active", "done", "paused"}:
                state = "queued"
            ev_ids = [eid for eid in (row.get("evidence_ids") or ()) if isinstance(eid, str) and eid in valid_attempt_ids]
            hyp_id = row.get("hypothesis_id")
            if not isinstance(hyp_id, str) or hyp_id not in valid_hyp_ids:
                hyp_id = None

            rec_id = row.get("record_id")
            expected_rev = None
            target_id = None
            if (
                isinstance(rec_id, str)
                and rec_id in by_id
                and by_id[rec_id].kind == "route"
                and details.get(rec_id, {}).get("status") in {"active", "degraded"}
            ):
                target_id = rec_id
                expected_rev = by_id[rec_id].revision

            payload = {
                "action": action,
                "rationale": rationale,
                "state": state,
                "evidence_ids": list(dict.fromkeys(ev_ids)),
                "tags": _clean_tags(row.get("tags"), "consolidator_route"),
            }
            if hyp_id is not None:
                payload["hypothesis_id"] = hyp_id
            if exposure_refs:
                payload["context_exposure_ids"] = exposure_refs
            ev = store.append("route", self.run_id, payload, record_id=target_id, expected_revision=expected_rev)
            by_id[ev.record_id] = ev
            admitted["routes"].append(ev.record_id)

        if has_refutation_or_contradiction:
            for regime in bundle.get("obstructed_regimes") or ():
                if isinstance(regime, str) and regime in _KNOWN_REGIMES:
                    admitted["obstructed_regimes"].append(regime)
            admitted["obstructed_regimes"] = list(dict.fromkeys(admitted["obstructed_regimes"]))

        return admitted

    async def maybe_consolidate(
        self,
        *,
        stagnation_monitor: Any = None,
        claim_constraints: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        triggered, reason = self.should_consolidate(stagnation_monitor=stagnation_monitor)
        if not triggered:
            return {"triggered": False}

        with MemoryStore(self.database_path) as store:
            records = store.snapshot(run_id=self.run_id)
            details = store.integrity_details(records=records)
            last_cutoff = self._last_checkpoint_cutoff(records, details)
            new_attempt_ids = [
                e.record_id for e in records
                if e.kind == "attempt"
                and e.sequence > last_cutoff
                and details.get(e.record_id, {}).get("status") not in {"revoked", "needs_review"}
            ]
            curated = self.deterministic_curate(store, last_cutoff=last_cutoff)
            digest_prompt, prompt_exposed_ids = self._build_digest_prompt(
                store.snapshot(run_id=self.run_id),
                store.integrity_details(),
                last_cutoff,
                stagnation_monitor,
                claim_constraints,
            )

        llm_admitted: dict[str, Any] = {"lessons": [], "hypotheses": [], "routes": [], "obstructed_regimes": [], "used_llm": False}
        if self._has_llm_budget():
            try:
                response = await self.gateway.generate(
                    CONSOLIDATOR_SYSTEM_PROMPT,
                    [{"role": "user", "content": digest_prompt}],
                )
                llm_text = getattr(response, "text", str(response))
                parsed = _extract_json_object(llm_text)
                if parsed is not None:
                    with MemoryStore(self.database_path) as store:
                        llm_admitted = self._admit_llm_bundle(store, parsed, prompt_exposed_ids)
                        llm_admitted["used_llm"] = True
            except StopRun as error:
                if str(error) == "interrupted" or (self.state is not None and self.state.data.get("fatal")):
                    raise
            except (RuntimeError, ValueError, KeyError):
                pass

        with MemoryStore(self.database_path) as store:
            through_seq = store.sequence
            snap = store.snapshot(run_id=self.run_id)
            snap_details = store.integrity_details(records=snap)
            valid_cp_evidence = [
                e.record_id for e in snap
                if e.kind == "attempt"
                and e.record_id in set(new_attempt_ids)
                and e.sequence <= through_seq
                and snap_details.get(e.record_id, {}).get("status") in {"active", "degraded"}
            ][:16]
            cp = store.append(
                "checkpoint",
                self.run_id,
                {
                    "through_sequence": through_seq,
                    "trigger": reason,
                    "evidence_ids": valid_cp_evidence,
                },
            )

        return {
            "triggered": True,
            "reason": reason,
            "checkpoint_id": cp.record_id,
            "through_sequence": through_seq,
            "curated": curated,
            "llm": llm_admitted,
        }
