"""Budget-aware ExperimentSelector managing L1 witnesses, diagnostic probes, and L3 conjectures."""
import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pathweaver.core.contracts import atomic_json, digest, read_json
from pathweaver.core.ddmin import ddmin_reduce
from pathweaver.core.research_records import canonical_json
from pathweaver.research.claims import build_empirical_conjecture_bundle
from pathweaver.research.memory.store import MemoryStore

try:
    from pathweaver.research.run_state import StopRun
except ImportError:
    class StopRun(BaseException):
        pass


class ExperimentSelector:
    """Allocates bounded diagnostic quota to witness reduction, controlled comparison, and conjecture emission."""

    def __init__(self, state: Any, *, max_diagnostic_ratio: float = 0.15):
        self.state = state
        self.max_diagnostic_ratio = max(0.0, min(0.5, float(max_diagnostic_ratio)))
        self.witness_bank: dict[str, dict[str, Any]] = {}
        self.diagnostic_executions: int = 0
        self.emitted_claim_ids: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_diagnostic_ratio": self.max_diagnostic_ratio,
            "witness_bank": dict(self.witness_bank),
            "diagnostic_executions": self.diagnostic_executions,
            "emitted_claim_ids": list(self.emitted_claim_ids),
        }

    def load_state(self, raw: Mapping[str, Any]) -> None:
        if not isinstance(raw, Mapping):
            return
        self.diagnostic_executions = int(raw.get("diagnostic_executions", 0))
        bank = raw.get("witness_bank")
        self.witness_bank = {str(k): dict(v) for k, v in bank.items() if isinstance(v, Mapping)} if isinstance(bank, Mapping) else {}
        claims = raw.get("emitted_claim_ids")
        self.emitted_claim_ids = [str(c) for c in claims if isinstance(c, str)] if isinstance(claims, list) else []

    def _can_run_diagnostic(self, count: int = 1) -> bool:
        diag_cap = int(self.state.config.budget.max_instance_executions * self.max_diagnostic_ratio)
        if diag_cap < count or self.diagnostic_executions + count > diag_cap:
            return False
        if self.state.data["candidate_evaluations"] >= self.state.config.budget.max_candidate_evaluations:
            return False
        if self.state.data["instance_executions"] + count > self.state.config.budget.max_instance_executions:
            return False
        try:
            return self.state.remaining() > 2.0
        except StopRun:
            return False

    def _read_candidate_source(self, source_ref: str) -> str | None:
        if source_ref and not source_ref.startswith("rejected-source-sha256:"):
            path = Path(source_ref)
            if path.is_file():
                return path.read_text(encoding="utf-8")
        return None

    def _maybe_emit_conjecture(self, run_id: str, stagnation_monitor: Any) -> str | None:
        if stagnation_monitor is None:
            return None
        pos_rows = [
            row for row in stagnation_monitor.history
            if isinstance(row.get("bound_gap"), int) and row["bound_gap"] > 0 and row.get("objectives") is not None
        ]
        if len(pos_rows) < 4:
            return None
        regimes = sorted({str(row.get("regime", "general_constructive")) for row in pos_rows})
        if len(regimes) < 2:
            return None
        min_gap = min(int(row["bound_gap"]) for row in pos_rows)
        at_min = [row for row in pos_rows if int(row["bound_gap"]) == min_gap]
        if len(at_min) < 2:
            return None

        claim_id = f"empirical-gap-{self.state.config.task_id}-{digest(run_id.encode('utf-8'))[:8]}"
        if claim_id in self.emitted_claim_ids:
            return None

        evidence_name = "candidate_claim_evidence.md"
        evidence_path = self.state.root / evidence_name
        evidence_md = (
            f"# Empirical Persistent Bound Gap Note ({claim_id})\n\n"
            f"- Task: `{self.state.config.task_id}`\n"
            f"- Run ID: `{run_id}`\n"
            f"- Distinct regimes evaluated with positive gap: {', '.join(regimes)}\n"
            f"- Minimum observed bound gap across {len(pos_rows)} feasible evaluations: `{min_gap}` "
            f"({len(at_min)} evaluations stalled at this exact gap).\n\n"
            "This note records an empirical draft conjecture requiring independent mathematical proof "
            "or an exact dual/Lean certificate before promotion.\n"
        )
        evidence_path.write_text(evidence_md, encoding="utf-8")
        bundle = build_empirical_conjecture_bundle(
            claim_id=claim_id,
            statement=(
                f"Across {len(regimes)} distinct algorithmic regimes ({', '.join(regimes)}), "
                f"feasible candidates on the training suite hit an unclosed minimum bound gap of {min_gap}."
            ),
            scope=f"Frozen training suite for task {self.state.config.task_id} under run {run_id}.",
            gap="Empirical finite-suite observation only; dual tightening or formal obstruction proof is pending.",
            summary=f"Minimum bound_gap={min_gap} observed across {len(pos_rows)} evaluations in {len(regimes)} regimes.",
            evidence_rel_path=evidence_name,
        )
        atomic_json(self.state.root / "candidate_claims.json", bundle)
        self.emitted_claim_ids.append(claim_id)
        return claim_id

    async def step(
        self,
        *,
        evaluator: Any,
        database_path: str | Path,
        run_id: str,
        stagnation_monitor: Any = None,
        context_adapter: Any = None,
    ) -> dict[str, Any]:
        db_path = Path(database_path)
        with MemoryStore(db_path, readonly=True) as store:
            records = store.snapshot(run_id=run_id)
            details = store.integrity_details(records=records)

        fitness_attempts = [
            e for e in records
            if e.kind == "attempt"
            and e.payload.get("dataset_role", "fitness") == "fitness"
            and details.get(e.record_id, {}).get("status") in {"active", "degraded"}
        ]
        if not fitness_attempts:
            return {"action": "noop", "reason": "no_fitness_attempts"}

        latest_att = fitness_attempts[-1]
        latest_delta = (latest_att.payload.get("diagnostics") or {}).get("delta") or {}

        # Action 2: Controlled comparison on a reproduced reduced witness when a candidate targets it.
        if latest_att.payload.get("outcome") == "feasible":
            by_id = {e.record_id: e for e in records}
            for b_id, witness in self.witness_bank.items():
                if not witness.get("reproduced"):
                    continue
                hyp_id = witness.get("hypothesis_id")
                if not hyp_id or hyp_id not in by_id:
                    continue
                hyp = by_id[hyp_id]
                if hyp.payload.get("state") != "open":
                    continue
                if latest_att.record_id == witness.get("source_attempt_id"):
                    continue
                if latest_att.record_id in witness.get("compared_attempt_ids", ()):
                    continue
                improved = set(latest_delta.get("improved_instances") or ())
                if b_id not in improved and latest_att.payload.get("hypothesis_id") != hyp_id:
                    continue
                source = self._read_candidate_source(str(latest_att.payload.get("source_ref", "")))
                if source is None or not self._can_run_diagnostic(1):
                    continue
                diag_doc = await evaluator.run_diagnostic(
                    source,
                    [witness["reduced_instance"]],
                    dataset_id=witness["diag_dataset_id"],
                    hypothesis_id=hyp_id,
                    parent_id=witness["witness_attempt_id"],
                    extra_tags=(f"bottleneck_inst:{b_id}", "diag_probe:controlled_compare"),
                )
                self.diagnostic_executions += 1
                witness.setdefault("compared_attempt_ids", []).append(latest_att.record_id)

                d_payload = diag_doc["payload"]
                d_delta = (d_payload.get("diagnostics") or {}).get("delta") or {}
                d_gap = d_delta.get("total_bound_gap")
                w_gap = witness.get("witness_gap")
                d_objs = d_payload.get("objectives")
                w_objs = witness.get("witness_objectives")
                resolved = False
                if d_payload.get("outcome") == "feasible":
                    if d_gap is not None and w_gap is not None:
                        resolved = d_gap < w_gap or d_gap == 0
                    elif d_objs is not None and w_objs is not None:
                        resolved = tuple(d_objs) < tuple(w_objs)
                    else:
                        resolved = True

                with MemoryStore(db_path) as store:
                    cur_hyp = store.get(hyp_id)
                    cur_det = store.integrity_details()
                    if d_payload.get("verification") == "verified" and cur_det.get(hyp_id, {}).get("status") in {"active", "degraded"}:
                        updated = dict(cur_hyp.payload)
                        sup = list(updated.get("support_ids") or ())
                        con = list(updated.get("contradiction_ids") or ())
                        if resolved and diag_doc["attempt_id"] not in sup:
                            sup.append(diag_doc["attempt_id"])
                            updated["support_ids"] = sup
                            if not con:
                                updated["state"] = "supported"
                        elif not resolved and diag_doc["attempt_id"] not in con:
                            con.append(diag_doc["attempt_id"])
                            updated["contradiction_ids"] = con
                        store.append("hypothesis", run_id, updated, record_id=hyp_id, expected_revision=cur_hyp.revision)

                    for ev in store.snapshot(run_id=run_id):
                        if (
                            ev.kind == "route"
                            and ev.payload.get("hypothesis_id") == hyp_id
                            and ev.payload.get("action") == "controlled_compare"
                            and ev.payload.get("state") in {"queued", "active"}
                        ):
                            r_upd = dict(ev.payload)
                            r_upd["state"] = "done"
                            ev_ids = list(r_upd.get("evidence_ids") or ())
                            if diag_doc["attempt_id"] not in ev_ids:
                                ev_ids.append(diag_doc["attempt_id"])
                            r_upd["evidence_ids"] = ev_ids
                            store.append("route", run_id, r_upd, record_id=ev.record_id, expected_revision=ev.revision)

                if context_adapter is not None and resolved:
                    context_adapter.active_experiment_directive = ""
                emitted_claim = self._maybe_emit_conjecture(run_id, stagnation_monitor)
                return {
                    "action": "controlled_compare",
                    "instance_id": b_id,
                    "diagnostic_attempt_id": diag_doc["attempt_id"],
                    "resolved": resolved,
                    "emitted_claim_id": emitted_claim,
                }

        # Action 1: Failure / bottleneck witness reduction and reproduction.
        target_att = None
        for att in reversed(fitness_attempts):
            if att.payload.get("outcome") in {"feasible", "invalid"}:
                target_att = att
                break
        if target_att is not None and callable(getattr(evaluator.task, "reduce_instance", None)) and self._can_run_diagnostic(1):
            eval_path = self.state.root / "evaluations" / f"{target_att.record_id}.json"
            if eval_path.is_file():
                eval_doc = read_json(eval_path)
                inst_eval_by_id = {row["instance_id"]: row for row in (eval_doc.get("instances") or ())}
                orig_by_id = {inst["instance_id"]: inst for inst in evaluator.instances}
                t_delta = (target_att.payload.get("diagnostics") or {}).get("delta") or {}

                candidate_bids: list[str] = [
                    row["instance_id"]
                    for row in (eval_doc.get("instances") or ())
                    if not (row.get("evaluation") or {}).get("feasible")
                ]
                for iid in t_delta.get("bottleneck_instances") or ():
                    if iid not in candidate_bids:
                        candidate_bids.append(iid)

                for b_id in candidate_bids:
                    if b_id in self.witness_bank or b_id not in orig_by_id or b_id not in inst_eval_by_id:
                        continue
                    reduced = evaluator.task.reduce_instance(orig_by_id[b_id], inst_eval_by_id[b_id]["evaluation"])
                    if reduced is None:
                        continue
                    source = self._read_candidate_source(str(target_att.payload.get("source_ref", "")))
                    if source is None:
                        continue
                    diag_dataset_id = f"diag-{digest(canonical_json(reduced).encode('utf-8'))[:12]}"
                    diag_doc = await evaluator.run_diagnostic(
                        source,
                        [reduced],
                        dataset_id=diag_dataset_id,
                        parent_id=target_att.record_id,
                        extra_tags=(f"bottleneck_inst:{b_id}", "diag_probe:reduction"),
                    )
                    self.diagnostic_executions += 1

                    d_payload = diag_doc["payload"]
                    d_delta = (d_payload.get("diagnostics") or {}).get("delta") or {}
                    d_gap = d_delta.get("total_bound_gap")
                    orig_feasible = bool(inst_eval_by_id[b_id]["evaluation"].get("feasible"))

                    def _is_reproduced(payload: Mapping[str, Any], delta: Mapping[str, Any], gap: Any) -> bool:
                        if not orig_feasible:
                            return payload.get("outcome") != "feasible"
                        return (
                            (isinstance(gap, int) and gap > 0)
                            or (gap is None and bool(payload.get("objectives") and payload["objectives"][0] > 0))
                        )

                    reproduced = _is_reproduced(d_payload, d_delta, d_gap)

                    if (
                        reproduced
                        and callable(getattr(evaluator.task, "subset_elements", None))
                        and callable(getattr(evaluator.task, "rebuild_from_subset", None))
                        and self._can_run_diagnostic(4)
                    ):
                        elements = list(evaluator.task.subset_elements(reduced))
                        if len(elements) >= 4:
                            best_dd = {
                                "instance": reduced,
                                "doc": diag_doc,
                                "payload": d_payload,
                                "delta": d_delta,
                                "gap": d_gap,
                                "dataset_id": diag_dataset_id,
                                "probes": 0,
                            }

                            def _dd_reproduces(subset: list[Any]) -> bool:
                                if len(subset) >= len(elements) or best_dd["probes"] >= 4 or not self._can_run_diagnostic(1):
                                    return len(subset) == len(elements)
                                candidate_inst = evaluator.task.rebuild_from_subset(reduced, subset)
                                if candidate_inst is None:
                                    return False
                                best_dd["probes"] += 1
                                sub_ds = f"diag-{digest(canonical_json(candidate_inst).encode('utf-8'))[:12]}"
                                sub_doc = evaluator.evaluate_diagnostic(
                                    source,
                                    [candidate_inst],
                                    dataset_id=sub_ds,
                                    parent_id=target_att.record_id,
                                    extra_tags=(f"bottleneck_inst:{b_id}", "diag_probe:ddmin"),
                                )
                                self.diagnostic_executions += 1
                                sp = sub_doc["payload"]
                                sd = (sp.get("diagnostics") or {}).get("delta") or {}
                                sg = sd.get("total_bound_gap")
                                if _is_reproduced(sp, sd, sg):
                                    best_dd.update(
                                        instance=candidate_inst,
                                        doc=sub_doc,
                                        payload=sp,
                                        delta=sd,
                                        gap=sg,
                                        dataset_id=sub_ds,
                                    )
                                    return True
                                return False

                            await asyncio.to_thread(
                                ddmin_reduce, elements, _dd_reproduces, min_size=2, max_probes=4,
                            )
                            reduced = best_dd["instance"]
                            diag_doc = best_dd["doc"]
                            d_payload = best_dd["payload"]
                            d_delta = best_dd["delta"]
                            d_gap = best_dd["gap"]
                            diag_dataset_id = best_dd["dataset_id"]

                    entry: dict[str, Any] = {
                        "source_instance_id": b_id,
                        "source_attempt_id": target_att.record_id,
                        "reduced_instance": reduced,
                        "diag_dataset_id": diag_dataset_id,
                        "witness_attempt_id": diag_doc["attempt_id"],
                        "witness_objectives": d_payload.get("objectives"),
                        "witness_gap": d_gap,
                        "reproduced": reproduced,
                        "compared_attempt_ids": [],
                    }
                    if reproduced:
                        regime = str(d_delta.get("regime", "general_constructive"))
                        with MemoryStore(db_path) as store:
                            hyp_ev = store.append(
                                "hypothesis",
                                run_id,
                                {
                                    "statement": (
                                        f"Bottleneck on {b_id} persists on reduced witness {reduced['instance_id']} "
                                        f"(outcome={d_payload.get('outcome')}, objs={d_payload.get('objectives')}, gap={d_gap})."
                                    ),
                                    "test_plan": (
                                        f"Modify the algorithm mechanism beyond parameter tweaks to close the defect/gap "
                                        f"on {b_id} and its reduced witness {reduced['instance_id']}."
                                    ),
                                    "state": "open",
                                    "support_ids": [],
                                    "contradiction_ids": [],
                                    "tags": [f"bottleneck_inst:{b_id}", f"regime:{regime}", "witness_reduced"],
                                },
                            )
                            store.append(
                                "route",
                                run_id,
                                {
                                    "action": "controlled_compare",
                                    "rationale": (
                                        f"Reduced failure/gap witness {reduced['instance_id']} reproduces {b_id} bottleneck; "
                                        f"prioritize candidates resolving this isolated mechanism."
                                    ),
                                    "state": "queued",
                                    "hypothesis_id": hyp_ev.record_id,
                                    "evidence_ids": [diag_doc["attempt_id"]],
                                    "tags": [f"bottleneck_inst:{b_id}", "witness_reduced"],
                                },
                            )
                        entry["hypothesis_id"] = hyp_ev.record_id
                        if context_adapter is not None:
                            comment_prefix = "--" if getattr(evaluator.task, "candidate_language", "python") == "lean" else "#"
                            context_adapter.active_experiment_directive = (
                                f"- Active Hypothesis `{hyp_ev.record_id}`: reduced witness `{reduced['instance_id']}` "
                                f"(from `{b_id}`) reproduced outcome={d_payload.get('outcome')}, "
                                f"objectives={d_payload.get('objectives')}, bound_gap={d_gap}.\n"
                                f"- Declare `{comment_prefix} pathweaver-hypothesis: {hyp_ev.record_id}` at the top of your candidate "
                                "when proposing a structural fix for this bottleneck."
                            )
                    self.witness_bank[b_id] = entry
                    emitted_claim = self._maybe_emit_conjecture(run_id, stagnation_monitor)
                    return {
                        "action": "diagnose",
                        "instance_id": b_id,
                        "reproduced": reproduced,
                        "diagnostic_attempt_id": diag_doc["attempt_id"],
                        "emitted_claim_id": emitted_claim,
                    }

        # Action 3: Active adversarial instance synthesis probing current best candidate.
        best_meta = self.state.data.get("best")
        gen_adv_fn = getattr(evaluator.task, "generate_adversarial_instances", None)
        if (
            isinstance(best_meta, Mapping)
            and callable(gen_adv_fn)
            and self._can_run_diagnostic(2)
            and not any(key.startswith("adv__") for key in self.witness_bank)
        ):
            ext = getattr(evaluator.task, "candidate_extension", ".py")
            best_path = self.state.root / f"best{ext}"
            if best_path.is_file():
                best_source = best_path.read_text(encoding="utf-8")
                adv_seed = int(self.state.config.seed) + int(self.diagnostic_executions) * 37 + 11
                adv_instances = list(gen_adv_fn(seed=adv_seed, count=2) or ())
                for adv_inst in adv_instances:
                    if not self._can_run_diagnostic(1):
                        break
                    adv_id = f"adv__{adv_inst['instance_id']}"
                    diag_ds = f"diag-{digest(canonical_json(adv_inst).encode('utf-8'))[:12]}"
                    adv_doc = await evaluator.run_diagnostic(
                        best_source,
                        [adv_inst],
                        dataset_id=diag_ds,
                        parent_id=best_meta.get("attempt_id"),
                        extra_tags=(f"bottleneck_inst:{adv_id}", "diag_probe:adversarial"),
                    )
                    self.diagnostic_executions += 1
                    ap = adv_doc["payload"]
                    ad = (ap.get("diagnostics") or {}).get("delta") or {}
                    ag = ad.get("total_bound_gap")
                    hit_gap = ap.get("outcome") != "feasible" or (isinstance(ag, int) and ag > 0)
                    if hit_gap:
                        regime = str(ad.get("regime", "general_constructive"))
                        with MemoryStore(db_path) as store:
                            hyp_ev = store.append(
                                "hypothesis",
                                run_id,
                                {
                                    "statement": (
                                        f"Adversarial instance {adv_inst['instance_id']} exposes defect/gap on best candidate "
                                        f"(outcome={ap.get('outcome')}, objs={ap.get('objectives')}, gap={ag})."
                                    ),
                                    "test_plan": (
                                        f"Generalize algorithm logic to eliminate defect/gap on synthetic adversarial instance "
                                        f"{adv_inst['instance_id']} without regressing training fitness."
                                    ),
                                    "state": "open",
                                    "support_ids": [],
                                    "contradiction_ids": [],
                                    "tags": [f"bottleneck_inst:{adv_id}", f"regime:{regime}", "adversarial_witness"],
                                },
                            )
                        self.witness_bank[adv_id] = {
                            "source_instance_id": adv_id,
                            "source_attempt_id": best_meta.get("attempt_id"),
                            "reduced_instance": adv_inst,
                            "diag_dataset_id": diag_ds,
                            "witness_attempt_id": adv_doc["attempt_id"],
                            "witness_objectives": ap.get("objectives"),
                            "witness_gap": ag,
                            "reproduced": True,
                            "compared_attempt_ids": [],
                            "hypothesis_id": hyp_ev.record_id,
                        }
                        if context_adapter is not None:
                            comment_prefix = "--" if getattr(evaluator.task, "candidate_language", "python") == "lean" else "#"
                            context_adapter.active_experiment_directive = (
                                f"- Active Adversarial Hypothesis `{hyp_ev.record_id}`: unseen synthetic witness "
                                f"`{adv_inst['instance_id']}` exposed outcome={ap.get('outcome')}, "
                                f"objectives={ap.get('objectives')}, bound_gap={ag}.\n"
                                f"- Declare `{comment_prefix} pathweaver-hypothesis: {hyp_ev.record_id}` if your change addresses this case."
                            )
                        emitted_claim = self._maybe_emit_conjecture(run_id, stagnation_monitor)
                        return {
                            "action": "adversarial_probe",
                            "instance_id": adv_id,
                            "reproduced": True,
                            "diagnostic_attempt_id": adv_doc["attempt_id"],
                            "emitted_claim_id": emitted_claim,
                        }

        emitted_claim = self._maybe_emit_conjecture(run_id, stagnation_monitor)
        return {"action": "noop", "emitted_claim_id": emitted_claim}
