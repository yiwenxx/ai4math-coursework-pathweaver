"""Transactional, append-only SQLite ledger with revision and evidence links."""
from collections import OrderedDict
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Mapping
from uuid import uuid4

from pathweaver.core.research_records import (
    IMMUTABLE_KINDS, ResearchEvent, ResearchScope, canonical_json,
    require_id, validate_payload,
)

SCHEMA_VERSION = 2
_CACHE_LOCK = threading.RLock()
_SNAPSHOT_CACHE: OrderedDict[tuple[str, int, int, int, str | None], tuple[ResearchEvent, ...]] = OrderedDict()
_INTEGRITY_CACHE: OrderedDict[tuple[str, int, int, int], dict[str, dict[str, Any]]] = OrderedDict()
_MAX_STORE_CACHE = 32


def _file_sig(path: Path) -> tuple[int, int]:
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def _evict_path_cache(path_str: str) -> None:
    with _CACHE_LOCK:
        for cache in (_SNAPSHOT_CACHE, _INTEGRITY_CACHE):
            for key in [k for k in cache if k[0] == path_str]:
                cache.pop(key, None)
_SCHEMA = f"""
CREATE TABLE events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    run_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision > 0),
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    UNIQUE(record_id, revision)
);
CREATE INDEX events_run ON events(run_id, sequence);
CREATE INDEX events_record ON events(record_id, sequence);
CREATE TRIGGER no_event_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'research events are immutable'); END;
CREATE TRIGGER no_event_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'research events are immutable'); END;
PRAGMA user_version = {SCHEMA_VERSION};
"""


class MemoryStore:
    """Trusted-controller storage, not a security boundary against candidate code."""

    def __init__(self, path: str | Path, *, create: bool = False, readonly: bool = False):
        path = Path(path).resolve()
        self.path = path
        if create and readonly:
            raise ValueError("Cannot create a read-only store")
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        elif not path.is_file():
            raise FileNotFoundError(f"Memory database does not exist: {path}")
        uri = path.as_uri() + ("?mode=ro" if readonly else "?mode=rwc" if create else "?mode=rw")
        self.connection = sqlite3.connect(uri, uri=True, timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0 and create:
                self.connection.executescript("BEGIN IMMEDIATE;" + _SCHEMA + "COMMIT;")
            elif version != SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported memory schema {version}; expected {SCHEMA_VERSION}. "
                    "Database unchanged. Preserve it and export with its original application version; "
                    "create a new database for this version."
                )
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self) -> "MemoryStore":
        return self

    def __exit__(self, *_: Any) -> None:
        self.connection.close()

    @staticmethod
    def _event(row: sqlite3.Row) -> ResearchEvent:
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        return ResearchEvent(**data)

    @property
    def sequence(self) -> int:
        return self.connection.execute("SELECT COALESCE(MAX(sequence), 0) FROM events").fetchone()[0]

    def get(self, record_id: str, *, as_of: int | None = None) -> ResearchEvent:
        row = self.connection.execute(
            "SELECT * FROM events WHERE record_id=? AND sequence<=? ORDER BY sequence DESC LIMIT 1",
            (record_id, self.sequence if as_of is None else as_of),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown record at this cutoff: {record_id}")
        return self._event(row)

    def snapshot(self, *, as_of: int | None = None, run_id: str | None = None) -> list[ResearchEvent]:
        cutoff = self.sequence if as_of is None else as_of
        mtime_ns, size_bytes = _file_sig(self.path)
        cache_key = (str(self.path), mtime_ns, size_bytes, cutoff, run_id)
        with _CACHE_LOCK:
            cached = _SNAPSHOT_CACHE.get(cache_key)
            if cached is not None:
                _SNAPSHOT_CACHE.move_to_end(cache_key)
                return list(cached)
        sql = """SELECT e.* FROM events e
                 WHERE e.sequence<=? AND NOT EXISTS
                 (SELECT 1 FROM events n WHERE n.record_id=e.record_id
                  AND n.sequence>e.sequence AND n.sequence<=?)"""
        params: list[Any] = [cutoff, cutoff]
        if run_id is not None:
            sql += " AND e.run_id=?"
            params.append(run_id)
        rows = tuple(self._event(r) for r in self.connection.execute(sql + " ORDER BY e.sequence", params))
        with _CACHE_LOCK:
            _SNAPSHOT_CACHE[cache_key] = rows
            _SNAPSHOT_CACHE.move_to_end(cache_key)
            while len(_SNAPSHOT_CACHE) > _MAX_STORE_CACHE:
                _SNAPSHOT_CACHE.popitem(last=False)
        return list(rows)

    def integrity_details(
        self,
        *,
        as_of: int | None = None,
        records: list[ResearchEvent] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Derive graded revocation and implicit context taint without overwriting history.

        Statuses:
        - ``revoked``: directly targeted by an ``invalidation`` event.
        - ``needs_review``: run revoked, or all direct supports lost (hard quarantine).
        - ``degraded``: partial direct support lost (or minor boundary/superseded drift with
          remaining support or replacement), retained in retrieval with confidence penalty.
        - ``context_tainted``: non-verified LLM hypothesis/lesson/route/unverified attempt whose
          prompt-window ``context_exposure_ids`` included a fatally revoked/tainted record.
        - ``active``: clean evidence and clean context exposure.
        """
        cache_key: tuple[str, int, int, int] | None = None
        if records is None:
            cutoff = self.sequence if as_of is None else as_of
            mtime_ns, size_bytes = _file_sig(self.path)
            cache_key = (str(self.path), mtime_ns, size_bytes, cutoff)
            with _CACHE_LOCK:
                cached = _INTEGRITY_CACHE.get(cache_key)
                if cached is not None:
                    _INTEGRITY_CACHE.move_to_end(cache_key)
                    return copy.deepcopy(cached)
            records = self.snapshot(as_of=cutoff)
        by_id = {e.record_id: e for e in records}
        invalid_meta: dict[str, dict[str, Any]] = {}
        for event in records:
            if event.kind == "invalidation":
                target = event.payload["target_id"]
                if target in by_id:
                    invalid_meta[target] = {
                        "severity": event.payload.get("severity", "fatal"),
                        "replacement_id": event.payload.get("replacement_id"),
                        "reason": event.payload.get("reason", ""),
                    }

        statuses: dict[str, str] = {
            e.record_id: ("revoked" if e.record_id in invalid_meta else "active")
            for e in records
        }
        details: dict[str, dict[str, Any]] = {
            e.record_id: {
                "status": statuses[e.record_id],
                "active_supports": 0,
                "total_supports": len(e.support_dependencies),
                "revoked_refs": [],
                "replaced_refs": [],
                "tainted_by": [],
            }
            for e in records
        }

        while True:
            changed = False
            for e in records:
                if e.kind == "invalidation" or e.record_id in invalid_meta:
                    continue
                new_status = "active"
                revoked_refs: list[str] = []
                replaced_refs: list[str] = []
                tainted_by: list[str] = []
                active_supports = 0

                if e.kind != "run" and statuses.get(e.run_id) in {"revoked", "needs_review"}:
                    new_status = "needs_review"
                    revoked_refs = [e.run_id]
                elif e.kind in {"hypothesis", "lesson"}:
                    supports = e.support_dependencies
                    for ref in supports:
                        ref_status = statuses.get(ref)
                        meta = invalid_meta.get(ref)
                        rep = meta.get("replacement_id") if meta else None
                        if ref_status in {"active", "degraded"}:
                            active_supports += 1
                        elif rep and statuses.get(rep) in {"active", "degraded"}:
                            active_supports += 1
                            replaced_refs.append(ref)
                        else:
                            revoked_refs.append(ref)
                    if supports:
                        if active_supports == 0:
                            new_status = "needs_review"
                        elif revoked_refs or replaced_refs:
                            new_status = "degraded"
                elif e.kind == "route":
                    hyp_id = e.payload.get("hypothesis_id")
                    ev_ids = tuple(e.payload.get("evidence_ids") or ())
                    hyp_lost = bool(hyp_id and statuses.get(hyp_id) in {"revoked", "needs_review"})
                    ev_lost = [ref for ref in ev_ids if statuses.get(ref) in {"revoked", "needs_review"}]
                    ev_deg = [ref for ref in ev_ids if statuses.get(ref) == "degraded"]
                    if hyp_lost or (ev_ids and len(ev_lost) == len(ev_ids)):
                        new_status = "needs_review"
                        revoked_refs = ([hyp_id] if hyp_lost else []) + ev_lost
                    elif ev_lost or ev_deg or (hyp_id and statuses.get(hyp_id) in {"degraded", "context_tainted"}):
                        new_status = "degraded"
                        revoked_refs = ev_lost
                elif e.kind == "checkpoint":
                    ev_lost = [ref for ref in e.dependencies if statuses.get(ref) in {"revoked", "needs_review"}]
                    if ev_lost:
                        new_status = "needs_review"
                        revoked_refs = ev_lost

                # Implicit prompt-window taint tracking: independent host verification breaks semantic taint.
                is_verified_attempt = e.kind == "attempt" and e.payload.get("verification") == "verified"
                if new_status != "needs_review" and not is_verified_attempt and e.context_exposures:
                    for ref in e.context_exposures:
                        ref_status = statuses.get(ref)
                        meta = invalid_meta.get(ref)
                        if ref_status in {"needs_review", "context_tainted"}:
                            tainted_by.append(ref)
                        elif ref_status == "revoked":
                            rep = meta.get("replacement_id") if meta else None
                            if not (meta and meta.get("severity") == "superseded" and rep and statuses.get(rep) == "active"):
                                tainted_by.append(ref)
                    if tainted_by:
                        new_status = "context_tainted"

                prev = details[e.record_id]
                if (
                    statuses[e.record_id] != new_status
                    or prev["active_supports"] != active_supports
                    or prev["revoked_refs"] != revoked_refs
                    or prev["replaced_refs"] != replaced_refs
                    or prev["tainted_by"] != tainted_by
                ):
                    statuses[e.record_id] = new_status
                    details[e.record_id] = {
                        "status": new_status,
                        "active_supports": active_supports,
                        "total_supports": len(e.support_dependencies),
                        "revoked_refs": revoked_refs,
                        "replaced_refs": replaced_refs,
                        "tainted_by": tainted_by,
                    }
                    changed = True
            if not changed:
                break
        if cache_key is not None:
            with _CACHE_LOCK:
                _INTEGRITY_CACHE[cache_key] = copy.deepcopy(details)
                _INTEGRITY_CACHE.move_to_end(cache_key)
                while len(_INTEGRITY_CACHE) > _MAX_STORE_CACHE:
                    _INTEGRITY_CACHE.popitem(last=False)
        return details

    def integrity(self, *, as_of: int | None = None) -> dict[str, str]:
        """Derive graded revocation statuses; never overwrite historical evidence."""
        return {record_id: info["status"] for record_id, info in self.integrity_details(as_of=as_of).items()}

    def create_run(
        self, scope: ResearchScope, *, seed: int, objective_directions: tuple[str, ...],
        provenance: str = "experiment", run_id: str | None = None,
    ) -> ResearchEvent:
        run_id = run_id or f"run-{uuid4().hex}"
        return self.append("run", run_id, {
            "scope": scope.as_dict(), "seed": seed, "provenance": provenance,
            "objective_directions": list(objective_directions),
        }, record_id=run_id)

    def append(
        self, kind: str, run_id: str, payload: Mapping[str, Any], *,
        record_id: str | None = None, expected_revision: int | None = None,
    ) -> ResearchEvent:
        data = validate_payload(kind, payload)
        record_id = require_id(record_id or f"{kind}-{uuid4().hex}")
        require_id(run_id)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            old = self.connection.execute(
                "SELECT * FROM events WHERE record_id=? ORDER BY sequence DESC LIMIT 1", (record_id,),
            ).fetchone()
            if old:
                if old["kind"] != kind or old["run_id"] != run_id:
                    raise ValueError("A revision cannot change record kind or run")
                if kind in IMMUTABLE_KINDS:
                    raise ValueError(f"{kind} records are immutable; append a new observation instead")
                if expected_revision != old["revision"]:
                    raise ValueError("Updating a record requires its current expected_revision")
            elif expected_revision not in (None, 0):
                raise ValueError("New records have no prior revision")
            revision = old["revision"] + 1 if old else 1
            event = ResearchEvent(0, record_id, kind, run_id, revision, "", data)
            self._validate_links(event)
            created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            self.connection.execute(
                "INSERT INTO events(record_id,kind,run_id,revision,created_at,payload) VALUES(?,?,?,?,?,?)",
                (record_id, kind, run_id, revision, created_at, canonical_json(data)),
            )
            result = self.get(record_id)
            self.connection.execute("COMMIT")
            _evict_path_cache(str(self.path))
            return result
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise

    def _validate_links(self, event: ResearchEvent) -> None:
        if event.kind == "run":
            if event.record_id != event.run_id:
                raise ValueError("Run ID must equal its record ID")
            return
        records = self.snapshot()
        by_id = {r.record_id: r for r in records}

        def _require_rec(ref_id: str) -> ResearchEvent:
            rec = by_id.get(ref_id)
            if rec is None:
                raise ValueError(f"Unknown record at this cutoff: {ref_id}")
            return rec

        run = _require_rec(event.run_id)
        if run.kind != "run":
            raise ValueError("run_id must reference a run")
        states = {rid: info["status"] for rid, info in self.integrity_details(records=records).items()}
        if event.kind != "invalidation" and states.get(run.record_id) != "active":
            raise ValueError("Run evidence has been invalidated; create a new run")
        evidential_ids = [
            ref for ref in event.references if ref not in set(event.context_exposures)
        ]
        refs = [_require_rec(ref) for ref in evidential_ids]
        if any(ref.run_id != event.run_id for ref in refs):
            raise ValueError("Evidence links must stay within a run; transfer advice must be re-evaluated")
        if event.record_id in event.references:
            raise ValueError("A record cannot reference itself")
        # Revisions must not introduce a dependency cycle.
        pending = list(event.references)
        seen: set[str] = set()
        while pending:
            ref = pending.pop()
            if ref == event.record_id:
                raise ValueError("Evidence dependencies cannot form a cycle")
            if ref not in seen:
                seen.add(ref)
                if ref in by_id:
                    pending.extend(by_id[ref].references)
        data = event.payload
        if event.kind == "invalidation":
            target = _require_rec(data["target_id"])
            if target.kind == "invalidation":
                raise ValueError("Invalidations cannot target another invalidation")
            if data.get("replacement_id"):
                rep = _require_rec(data["replacement_id"])
                if rep.kind != target.kind or rep.record_id == target.record_id:
                    raise ValueError("replacement_id must reference a distinct record of the same kind")
                if states.get(rep.record_id) in {"revoked", "needs_review"}:
                    raise ValueError("replacement_id must reference an active or degraded record")
        if event.kind == "attempt":
            scope = run.payload["scope"]
            if data.get("dataset_role", "fitness") == "fitness" and data["dataset_id"] != scope["fitness_dataset_id"]:
                raise ValueError("Attempt dataset must match the run's fitness dataset")
            if data.get("objectives") is not None and len(data["objectives"]) != len(run.payload["objective_directions"]):
                raise ValueError("Objective dimensions must match the run contract")
            if run.payload["provenance"] == "illustrative" and data["verification"] != "illustrative":
                raise ValueError("Illustrative runs cannot supply verified research evidence")
            if data.get("parent_id") and _require_rec(data["parent_id"]).kind != "attempt":
                raise ValueError("Invalid parent_id reference")
            if data.get("hypothesis_id") and _require_rec(data["hypothesis_id"]).kind != "hypothesis":
                raise ValueError("Invalid hypothesis_id reference")
        if event.kind in {"hypothesis", "lesson", "route", "checkpoint"}:
            if data.get("hypothesis_id") and _require_rec(data["hypothesis_id"]).kind != "hypothesis":
                raise ValueError("hypothesis_id must reference a hypothesis")
            for field in ("support_ids", "contradiction_ids", "evidence_ids"):
                for ref_id in data.get(field) or ():
                    if _require_rec(ref_id).kind != "attempt":
                        raise ValueError("Support, contradiction and evidence IDs must reference attempts")
        for ref_id in event.context_exposures:
            if _require_rec(ref_id).kind not in {"attempt", "hypothesis", "lesson", "route"}:
                raise ValueError("context_exposure_ids must reference attempt, hypothesis, lesson, or route records")
        if event.kind == "checkpoint" and not run.sequence <= data["through_sequence"] <= self.sequence:
            raise ValueError("Checkpoint cutoff must lie within recorded history")
        if event.kind == "checkpoint" and any(ref.sequence > data["through_sequence"] for ref in refs):
            raise ValueError("Checkpoint evidence cannot postdate its cutoff")
        admission = []
        if event.kind == "lesson" and data["state"] == "experimental":
            admission = data.get("support_ids", [])
        elif event.kind == "hypothesis" and data["state"] in {"supported", "refuted"}:
            admission = data.get("support_ids" if data["state"] == "supported" else "contradiction_ids", [])
            if not admission:
                raise ValueError("Supported/refuted hypotheses need corresponding evidence")
        if any(_require_rec(ref).payload.get("verification") != "verified" or states.get(ref) not in {"active", "degraded"} for ref in admission):
            raise ValueError("Evidence admission requires active attempts from a trusted evaluator")

    def invalidate(
        self,
        record_id: str,
        reason: str,
        *,
        severity: str = "fatal",
        replacement_id: str | None = None,
    ) -> ResearchEvent:
        target = self.get(record_id)
        if target.kind == "invalidation":
            raise ValueError("Invalidations cannot be undone; append corrected evidence in a new record")
        payload: dict[str, Any] = {"target_id": record_id, "reason": reason, "severity": severity}
        if replacement_id is not None:
            payload["replacement_id"] = replacement_id
        return self.append("invalidation", target.run_id, payload)

    def export_jsonl(self) -> str:
        """Lossless ledger export, including all superseded revisions."""
        return "\n".join(canonical_json(self._event(row).as_dict())
                         for row in self.connection.execute("SELECT * FROM events ORDER BY sequence"))
