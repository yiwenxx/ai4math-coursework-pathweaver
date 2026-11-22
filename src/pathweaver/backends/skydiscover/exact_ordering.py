"""Local extension of the pinned AdaEvolve quality-ordering hooks.

Incumbent winner selection (`get_best_program`, `_update_best_program`, and final
`best.py`) strictly compares raw integer objective tuples `(1, -T, -L, ...)`.
To prevent premature diversity collapse under strict lexicographic dominance,
archives simultaneously maintain an exact-integer Pareto stepping-stone layer:
- Rank-0 Pareto non-dominated programs (strictly better on a secondary objective
  or per-instance coordinate without float rounding) are protected from eviction
  up to a bounded archive cap and blended into elite retention scores.
- Context sampling includes top stepping stones so the LLM can synthesize their
  secondary-objective mechanisms into the primary-objective leader.
No upstream module, function or class is monkeypatched.
"""
from pathlib import Path

from pathweaver.core.contracts import atomic_json as _atomic_json, read_json as _read_json


class _QualityKey(tuple):
    def __format__(self, specification):
        # The pinned database uses numeric formats in diagnostic log messages.
        # Display the actual tuple rather than inventing a scalar quality value.
        return str(tuple(self))


def _exact_pareto_vector(program) -> tuple[int, ...] | None:
    """Extract lossless integer maximization vector for Pareto stepping-stone checks."""
    metrics = getattr(program, "metrics", None) or {}
    if metrics.get("validity") != 1:
        return None
    objs = metrics.get("exact_objectives")
    if not isinstance(objs, (list, tuple)) or not objs:
        return None
    if len(objs) >= 2:
        return tuple(-int(v) for v in objs)
    per_inst = metrics.get("per_instance_objectives")
    if isinstance(per_inst, (list, tuple)) and len(per_inst) >= 2:
        flat = [int(row[0]) for row in per_inst if isinstance(row, (list, tuple)) and row]
        if len(flat) == len(per_inst):
            return tuple(-v for v in flat)
    return (-int(objs[0]),)


def _dominates_exact(vec_a: tuple[int, ...], vec_b: tuple[int, ...]) -> bool:
    """Strict Pareto dominance on lossless integer maximization vectors."""
    better = False
    for a, b in zip(vec_a, vec_b):
        if a < b:
            return False
        if a > b:
            better = True
    return better


def compute_exact_pareto(programs) -> tuple[dict[str, int], dict[str, float]]:
    """Compute exact integer Pareto layers and normalized crowding distances."""
    vectors: dict[str, tuple[int, ...]] = {}
    invalid_ids: list[str] = []
    for p in programs:
        vec = _exact_pareto_vector(p)
        if vec is None:
            invalid_ids.append(p.id)
        else:
            vectors[p.id] = vec

    remaining = set(vectors.keys())
    ranks: dict[str, int] = {}
    layers: list[list[str]] = []
    rank = 0
    while remaining:
        front = []
        for pid_a in remaining:
            va = vectors[pid_a]
            if not any(_dominates_exact(vectors[pid_b], va) for pid_b in remaining if pid_b != pid_a):
                front.append(pid_a)
        for pid in front:
            ranks[pid] = rank
            remaining.discard(pid)
        layers.append(front)
        rank += 1
    for pid in invalid_ids:
        ranks[pid] = rank + 1

    crowding: dict[str, float] = {p.id: 0.0 for p in programs}
    if vectors:
        dims = len(next(iter(vectors.values())))
        for layer in layers:
            if len(layer) <= 2:
                for pid in layer:
                    crowding[pid] = float("inf")
                continue
            for m in range(dims):
                ordered = sorted(layer, key=lambda pid: vectors[pid][m])
                crowding[ordered[0]] = float("inf")
                crowding[ordered[-1]] = float("inf")
                span = vectors[ordered[-1]][m] - vectors[ordered[0]][m]
                if span <= 0:
                    continue
                for idx in range(1, len(ordered) - 1):
                    crowding[ordered[idx]] += (vectors[ordered[idx + 1]][m] - vectors[ordered[idx - 1]][m]) / span
    return ranks, crowding


def create_database(config, ordering, *, stepping_stone_weight: float = 0.45):
    """Import optional upstream types only when live discovery constructs a database."""
    from skydiscover.optimize.search.adaevolve.adaptation import MultiDimensionalAdapter
    from skydiscover.optimize.search.adaevolve.archive.unified_archive import UnifiedArchive
    from skydiscover.optimize.search.adaevolve.database import AdaEvolveDatabase

    w_step = float(stepping_stone_weight)

    class ExactArchive(UnifiedArchive):
        def _get_fitness(self, program):
            return _QualityKey(ordering.key(program.metrics))

        def _ensure_cache_valid(self) -> None:
            if self._cache_valid:
                return
            programs = list(self._programs.values())
            n = len(programs)
            if n == 0:
                self._cache_valid = True
                return
            self.diversity.update(programs)
            fitness_sorted = sorted(programs, key=lambda p: self._get_fitness(p), reverse=True)
            self._fitness_ranks = {p.id: i for i, p in enumerate(fitness_sorted)}
            self._pareto_ranks, self._crowding_distances = compute_exact_pareto(programs)
            entries = [
                (p.id, self._pareto_ranks.get(p.id, n), self._crowding_distances.get(p.id, 0.0))
                for p in programs
            ]
            entries.sort(key=lambda x: (x[1], -x[2]))
            denom = max(n - 1, 1)
            self._pareto_percentiles = {pid: 1.0 - (i / denom) for i, (pid, _, _) in enumerate(entries)}
            self._dominated_flags = {p.id: self._pareto_ranks.get(p.id, 1) > 0 for p in programs}
            self._novelty_scores = {p.id: self._compute_novelty(p, programs) for p in programs}
            self._elite_scores = {p.id: self._compute_elite_score(p, n) for p in programs}
            self._cache_valid = True

        def _compute_elite_score(self, program, n: int) -> float:
            lex_rank = self._fitness_ranks.get(program.id, n - 1)
            lex_pct = 1.0 - (lex_rank / max(n - 1, 1))
            pareto_pct = self._pareto_percentiles.get(program.id, lex_pct)
            quality_pct = (1.0 - w_step) * lex_pct + w_step * pareto_pct
            novelty = self._novelty_scores.get(program.id, 0.0)
            novelty_pct = self._novelty_to_percentile(novelty)
            fw = self.config.fitness_weight + self.config.pareto_weight
            return fw * quality_pct + self.config.novelty_weight * novelty_pct

        def _compute_elite_score_for_new(self, program) -> float:
            programs = list(self._programs.values())
            n = len(programs)
            if n == 0:
                return self.config.fitness_weight + self.config.pareto_weight + self.config.novelty_weight
            fitness = self._get_fitness(program)
            better_count = sum(1 for p in programs if self._get_fitness(p) > fitness)
            lex_pct = (1.0 if better_count == 0 else 0.0) if n == 1 else max(0.0, min(1.0, 1.0 - (better_count / (n - 1))))

            new_vec = _exact_pareto_vector(program)
            if new_vec is None:
                pareto_pct = 0.0
            else:
                dom_count = 0
                for p in programs:
                    pv = _exact_pareto_vector(p)
                    if pv is not None and _dominates_exact(pv, new_vec):
                        dom_count += 1
                pareto_pct = max(0.0, min(1.0, 1.0 - (dom_count / max(n, 1))))

            novelty = self._compute_novelty(program, programs)
            existing_nov = [self._novelty_scores.get(p.id, 0.0) for p in programs] if self._cache_valid else [self._compute_novelty(p, programs) for p in programs]
            novelty_pct = max(0.0, min(1.0, sum(1 for v in existing_nov if v < novelty) / n))
            quality_pct = (1.0 - w_step) * lex_pct + w_step * pareto_pct
            fw = self.config.fitness_weight + self.config.pareto_weight
            return fw * quality_pct + self.config.novelty_weight * novelty_pct

        def _get_protected_ids(self):
            self._ensure_cache_valid()
            protected = set()
            if self._elite_scores:
                elite_count = max(1, int(len(self._programs) * self.config.elite_ratio))
                sorted_ids = sorted(self._elite_scores.keys(), key=lambda pid: self._elite_scores[pid], reverse=True)
                protected.update(sorted_ids[:elite_count])
            if self._programs:
                best_id = max(self._programs.keys(), key=lambda pid: self._get_fitness(self._programs[pid]))
                protected.add(best_id)
            # Protect Rank-0 exact Pareto stepping stones up to a bounded cap so eviction never deadlocks.
            if w_step > 0.0 and self._pareto_ranks:
                front_ids = [pid for pid, r in self._pareto_ranks.items() if r == 0 and pid not in protected]
                front_ids.sort(key=lambda pid: (-self._crowding_distances.get(pid, 0.0), pid))
                raw_cap = max(1, int(self.config.max_size * 0.25))
                max_safe = max(0, self.config.max_size - 1 - len(protected))
                protected.update(front_ids[:min(raw_cap, max_safe)])
            return protected

        def sample_other_context_programs(self, parent, n: int = 5, top_k_ratio: float = 0.5):
            others = super().sample_other_context_programs(parent, n=n, top_k_ratio=top_k_ratio)
            if w_step <= 0.0 or n < 1:
                return others
            parent_vec = _exact_pareto_vector(parent)
            if parent_vec is None or len(parent_vec) < 2:
                return others
            self._ensure_cache_valid()
            existing_ids = {p.id for p in others} | {parent.id}
            # For multi-objective vectors (e.g. (T, L)), improve secondary coordinates (i >= 1).
            # For single-objective multi-instance vectors, check all instances starting at i = 0.
            parent_objs = (getattr(parent, "metrics", None) or {}).get("exact_objectives") or ()
            start_idx = 1 if len(parent_objs) >= 2 else 0
            stepping = []
            for p in self._programs.values():
                if p.id in existing_ids or self._pareto_ranks.get(p.id, 1) != 0:
                    continue
                pv = _exact_pareto_vector(p)
                if pv is not None and any(pv[i] > parent_vec[i] for i in range(start_idx, len(parent_vec))):
                    stepping.append((max(pv[i] - parent_vec[i] for i in range(start_idx, len(parent_vec))), p))
            if stepping:
                stepping.sort(key=lambda item: (-item[0], item[1].id))
                mate = stepping[0][1]
                others = [mate, *others][:n]
            return others

    class ProxyAdapter(MultiDimensionalAdapter):
        def record_evaluation(self, dim_idx, fitness):
            return super().record_evaluation(dim_idx, ordering.proxy(fitness))

        def receive_external_improvement(self, dim_idx, fitness):
            return super().receive_external_improvement(dim_idx, ordering.proxy(fitness))

    class ExactDatabase(AdaEvolveDatabase):
        def __init__(self, name, database_config):
            if database_config.db_path:
                raise ValueError("Use PathWeaver's explicit frozen-checkpoint restore")
            if getattr(database_config, "pareto_objectives", None):
                raise ValueError("Pareto selection cannot replace fixed-suite lexicographic ordering")
            super().__init__(name, database_config)
            self._restore_proxy_adapter()

        def _restore_proxy_adapter(self):
            self.adapter = ProxyAdapter.from_dict(self.adapter.to_dict())
            self.adapter.rng = self.rng

        def _wrap_archives(self):
            for index, archive in enumerate(self.archives):
                if isinstance(archive, ExactArchive):
                    continue
                if archive.config.pareto_objectives:
                    raise ValueError("Exact tuple archives do not enable Pareto selection")
                replacement = ExactArchive(archive.config, archive.diversity, self.rng)
                for program in archive.get_all():
                    ordering.key(program.metrics)
                    replacement._insert(program)
                replacement.set_genealogy_state(archive.get_genealogy_state())
                self.archives[index] = replacement

        def _init_archives(self, database_config):
            super()._init_archives(database_config)
            self._wrap_archives()

        def _seed_new_island(self, island_idx):
            # Upstream dynamic spawning constructs an archive directly. Replace
            # it before any seed is ranked or admitted, including after restore.
            self._wrap_archives()
            return super()._seed_new_island(island_idx)

        def _expand_to_island_count(self, target_count, metadata):
            super()._expand_to_island_count(target_count, metadata)
            self._wrap_archives()

        def _get_fitness(self, program):
            return _QualityKey(ordering.key(program.metrics))

        def _get_multiobjective_proxy_score(self, program):
            return ordering.proxy(self._get_fitness(program))

        def _sample_weighted(self, population):
            weights = [max(self.get_program_proxy_score(p), 0.001) for p in population]
            return self.rng.choices(population, weights=weights, k=1)[0]

        def _update_best_program(self, program):
            previous = self.programs.get(self.best_program_id)
            if previous is not None and self._get_fitness(program) <= self._get_fitness(previous):
                return False
            self.best_program_id = program.id
            # Upstream serializes/logs this field and passes it to its guidance
            # tracker. The exact winner is always selected by the tuples above.
            self._global_best_score = self.get_program_proxy_score(program)
            return True

        def get_best_program(self, metric=None):
            self._check_metric(metric)
            candidates = self._all_population_programs()
            previous = self.programs.get(self.best_program_id)
            if previous is not None:
                candidates.insert(0, previous)  # Preserve the tracked winner on ties/eviction.
            if not candidates:
                return None
            best = max(candidates, key=self._get_fitness)
            self.best_program_id = best.id
            self._global_best_score = self.get_program_proxy_score(best)
            return best

        @staticmethod
        def _check_metric(metric):
            if metric not in (None, "combined_score"):
                raise ValueError("Quality selection must use the declared exact objective ordering")

        def get_top_programs(self, n=10, metric=None):
            self._check_metric(metric)
            return super().get_top_programs(n, metric=None)

        def _contract_doc(self):
            doc = dict(ordering.describe())
            doc["stepping_stone_weight"] = w_step
            return doc

        def save(self, path=None, iteration=0, programs=None):
            destination = path or self.config.db_path
            if not destination:
                raise ValueError("An exact-ordering checkpoint needs an explicit path")
            super().save(destination, iteration, programs)
            _atomic_json(Path(destination) / "exact_ordering.json", self._contract_doc())

        def load(self, path):
            # A scalar-only checkpoint must not silently acquire new semantics.
            saved = _read_json(Path(path) / "exact_ordering.json")
            expected = self._contract_doc()
            # Accept legacy checkpoints matching ordering.describe() when w_step matches default or explicit key.
            if saved != expected and not ("stepping_stone_weight" not in saved and saved == ordering.describe()):
                raise ValueError("Checkpoint objective ordering does not match this fixed suite")
            super().load(path)
            self._restore_proxy_adapter()
            for program in self.programs.values():
                ordering.key(program.metrics)
            self.get_best_program()

    return ExactDatabase("adaevolve", config)
