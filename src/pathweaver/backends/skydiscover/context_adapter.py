"""Wrap an existing SkyDiscover context builder without editing upstream code.

Combines:
1. Dynamic failure-diagnostic retrieval from `MemoryStore` (including degraded multi-support lessons).
2. Prompt-window exposure tracking (`last_exposure_ids`, `last_through_sequence`) for implicit taint auditing.
3. Orthogonal paradigm-refactoring directives when `StructuralStagnationMonitor` detects a local-tweak trap.
4. Stepping-stone crossover annotations when secondary-objective Pareto mates are present in context.
"""
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pathweaver.research.context import build_context
from pathweaver.research.memory.retrieval import MemoryQuery
from pathweaver.research.memory.store import MemoryStore


_DIAGNOSTIC_TAG_HINTS = (
    ("timeout", "timeout"),
    ("wall_budget", "budget"),
    ("capacity", "capacity"),
    ("critical_path", "critical_path"),
    ("bottleneck", "bottleneck"),
    ("hall", "capacity"),
    ("uncovered", "coverage"),
    ("redundant", "local_search"),
    ("violation", "feasibility"),
    ("bound_gap", "optimality"),
    ("unsolved goals", "lean_goals"),
    ("type mismatch", "lean_type"),
    ("sorry", "lean_incomplete"),
    ("axiom", "lean_soundness"),
    ("formal_verified", "formal_verified"),
)


def _extract_program(current_program: Any) -> Any:
    if isinstance(current_program, Mapping) and len(current_program) == 1:
        only_val = next(iter(current_program.values()))
        if hasattr(only_val, "metrics") or isinstance(only_val, Mapping):
            return only_val
    return current_program


def _dynamic_query_signals(current_program: Any, context: Mapping[str, Any] | None) -> tuple[str, tuple[str, ...]]:
    """Extract compact diagnostic terms/tags from the current candidate without mutating inputs."""
    prog = _extract_program(current_program)
    snippets: list[str] = []
    tags: list[str] = []
    sources: list[Any] = []
    if prog is not None:
        sources.append(getattr(prog, "metrics", None))
        sources.append(getattr(prog, "artifacts", None))
        if isinstance(prog, Mapping):
            sources.append(prog.get("metrics"))
            sources.append(prog.get("artifacts"))
    if isinstance(context, Mapping):
        sources.append(context.get("artifacts"))
        sources.append(context.get("feedback"))
        sources.append(context.get("evaluation_artifacts"))

    for src in sources:
        if isinstance(src, str) and src.strip():
            snippets.append(src[:400])
        elif isinstance(src, Mapping):
            for key in ("feedback", "error", "violations", "termination", "bound_gap", "uncovered_edges", "redundant_vertices", "lean_messages"):
                val = src.get(key)
                if val:
                    snippets.append(f"{key} {str(val)[:220]}")

    combined = " ".join(snippets)
    lowered = combined.lower()
    for needle, tag in _DIAGNOSTIC_TAG_HINTS:
        if needle in lowered and tag not in tags:
            tags.append(tag)
    return combined[:600], tuple(tags)


def _stepping_stone_crossover_hint(current_program: Any, context: Mapping[str, Any] | None) -> str:
    """Annotate Pareto stepping-stone mates in context that improve secondary or per-instance coordinates."""
    if not isinstance(context, Mapping):
        return ""
    prog = _extract_program(current_program)
    parent_metrics = getattr(prog, "metrics", None) if prog is not None else None
    if parent_metrics is None and isinstance(prog, Mapping):
        parent_metrics = prog.get("metrics")
    if not isinstance(parent_metrics, Mapping) or parent_metrics.get("validity") != 1:
        return ""
    parent_objs = parent_metrics.get("exact_objectives")
    if not isinstance(parent_objs, (list, tuple)) or not parent_objs:
        return ""

    other_groups = context.get("other_context_programs")
    if not isinstance(other_groups, Mapping):
        return ""
    candidates: list[Any] = []
    for progs in other_groups.values():
        if isinstance(progs, Sequence) and not isinstance(progs, (str, bytes)):
            candidates.extend(progs)

    hints: list[str] = []
    for mate in candidates:
        m_metrics = getattr(mate, "metrics", None)
        if not isinstance(m_metrics, Mapping) or m_metrics.get("validity") != 1:
            continue
        m_objs = m_metrics.get("exact_objectives")
        if not isinstance(m_objs, (list, tuple)) or len(m_objs) != len(parent_objs):
            continue
        if len(parent_objs) >= 2 and any(int(m_objs[i]) < int(parent_objs[i]) for i in range(1, len(parent_objs))):
            deltas = [int(m_objs[i]) - int(parent_objs[i]) for i in range(len(parent_objs))]
            hints.append(
                f"- Context program `{getattr(mate, 'id', 'mate')[:8]}` is a Pareto stepping stone: "
                f"exact_objectives={list(m_objs)} vs parent {list(parent_objs)} (deltas {deltas}). "
                "Synthesize its secondary-objective mechanism while keeping the parent's primary-objective feasibility."
            )
        elif len(parent_objs) == 1:
            p_inst = parent_metrics.get("per_instance_objectives")
            m_inst = m_metrics.get("per_instance_objectives")
            if isinstance(p_inst, list) and isinstance(m_inst, list) and len(p_inst) == len(m_inst):
                wins = [i for i, (mv, pv) in enumerate(zip(m_inst, p_inst)) if mv and pv and int(mv[0]) < int(pv[0])]
                if wins:
                    hints.append(
                        f"- Context program `{getattr(mate, 'id', 'mate')[:8]}` outperforms parent on instance indices {wins}. "
                        "Inspect how it handles those structures."
                    )
    if not hints:
        return ""
    return "## PATHWEAVER STEPPING-STONE CROSSOVER HINT\n" + "\n".join(hints[:2])


class MemoryContextBuilder:
    """Duck-typed wrapper for the pinned build_prompt(program, context, **kwargs) API.

    This adapter adds context only. Evaluator recording, isolation and cost control
    remain controller responsibilities; it never starts a discovery run.
    """

    def __init__(self, base_builder: Any, database: str | Path, run_id: str, *,
                 query_text: str = "", tags: tuple[str, ...] = (), max_chars: int = 6000,
                 transfer_advice: bool = False, include_runs: tuple[str, ...] = (),
                 enabled: bool = True, dynamic_diagnostics: bool = True,
                 include_degraded: bool = True,
                 stagnation_monitor: Any = None,
                 paradigm_catalog: Sequence[dict[str, str]] = ()):
        self.base_builder = base_builder
        self.database = Path(database)
        self.run_id = run_id
        self.query_text = query_text
        self.tags = tags
        self.max_chars = max_chars
        self.transfer_advice = transfer_advice
        self.include_runs = include_runs
        self.enabled = enabled
        self.dynamic_diagnostics = dynamic_diagnostics
        self.include_degraded = include_degraded
        self.stagnation_monitor = stagnation_monitor
        self.paradigm_catalog = tuple(paradigm_catalog)
        self.last_exposure_ids: tuple[str, ...] = ()
        self.last_through_sequence: int | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_builder, name)

    def build_prompt(self, current_program: Any, context: dict[str, Any] | None = None,
                     **kwargs: Any) -> dict[str, str]:
        prompt = dict(self.base_builder.build_prompt(current_program, context, **kwargs))
        self.last_exposure_ids = ()
        self.last_through_sequence = None

        extra_sections: list[str] = []
        if self.enabled:
            query_text = self.query_text
            tags = tuple(self.tags)
            if self.dynamic_diagnostics:
                dyn_text, dyn_tags = _dynamic_query_signals(current_program, context)
                if dyn_text:
                    query_text = f"{query_text} {dyn_text}".strip()
                if dyn_tags:
                    tags = tuple(dict.fromkeys((*tags, *dyn_tags)))
            with MemoryStore(self.database, readonly=True) as store:
                packet = build_context(store, MemoryQuery(
                    run_id=self.run_id, text=query_text, tags=tags,
                    transfer_advice=self.transfer_advice, include_runs=self.include_runs,
                    include_degraded=self.include_degraded,
                ), max_chars=self.max_chars)
            self.last_exposure_ids = packet.record_ids
            self.last_through_sequence = packet.through_sequence
            extra_sections.append("## PATHWEAVER TRAINING MEMORY (EVIDENCE DATA)\n" + packet.text)

        crossover_hint = _stepping_stone_crossover_hint(current_program, context)
        if crossover_hint:
            extra_sections.append(crossover_hint)

        if self.stagnation_monitor is not None:
            directive = self.stagnation_monitor.detect_local_trap(self.paradigm_catalog)
            if directive is not None:
                extra_sections.append(directive.format_prompt_block())

        if extra_sections:
            # Separate from artifacts['feedback'], which pinned AdaEvolve truncates to 2000 chars.
            prompt["user"] += "\n\n" + "\n\n".join(extra_sections)
        return prompt


def attach_memory(controller: Any, database: str | Path, run_id: str, **options: Any) -> MemoryContextBuilder:
    base = controller.context_builder
    if isinstance(base, MemoryContextBuilder):
        raise ValueError("Research memory is already attached")
    if not callable(getattr(base, "build_prompt", None)):
        raise TypeError("Controller does not expose a compatible context builder")
    adapter = MemoryContextBuilder(base, database, run_id, **options)
    controller.context_builder = adapter
    return adapter
