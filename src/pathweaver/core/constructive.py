"""PatternBoost two-phase constructive witness search engine."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import random
from typing import Any, Protocol


@dataclass(frozen=True)
class WitnessRecord:
    """Verified candidate witness retained in the PatternBoost archive."""

    payload: Any
    feasible: bool
    energy: float | int
    objective: float | int
    descriptor: Any = None
    round_idx: int = 0


class ConstructiveWitnessTask(Protocol):
    """Domain-neutral interface for PatternBoost constructive witness tasks."""

    def random_seed_witness(self, rng: random.Random, size: int) -> Any: ...

    def local_refine(self, payload: Any, rng: random.Random, max_steps: int) -> Any: ...

    def recombine(self, elites: Sequence[WitnessRecord], rng: random.Random, round_idx: int) -> Any: ...

    def verify_witness(self, payload: Any) -> tuple[bool, float | int, float | int, Any]: ...


def _structural_key(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return (type(value).__name__, value)
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_structural_key(item) for item in value))
    if isinstance(value, Mapping):
        return (
            "map",
            tuple(sorted((_structural_key(k), _structural_key(v)) for k, v in value.items())),
        )
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_structural_key(item) for item in value), key=repr)))
    return ("repr", repr(value))


def _record_sort_key(record: WitnessRecord) -> tuple[bool, float | int, float | int, int]:
    return (not record.feasible, record.energy, record.objective, record.round_idx)


def run_patternboost(
    task: ConstructiveWitnessTask,
    *,
    rounds: int = 4,
    population_size: int = 12,
    elite_k: int = 4,
    local_steps: int = 200,
    seed: int = 0,
    size: int | None = None,
) -> dict[str, Any]:
    """Run alternating Local (Tabu/descent) and Global (elite recombination) PatternBoost rounds."""
    if type(rounds) is not int or rounds < 1:
        raise ValueError("rounds must be an integer >= 1")
    if type(population_size) is not int or population_size < 1:
        raise ValueError("population_size must be an integer >= 1")
    if type(elite_k) is not int or elite_k < 1:
        raise ValueError("elite_k must be an integer >= 1")
    if type(local_steps) is not int or local_steps < 0:
        raise ValueError("local_steps must be an integer >= 0")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    effective_elite_k = min(elite_k, population_size)
    target_size = size if size is not None else int(getattr(task, "n", getattr(task, "size", 0)))
    rng = random.Random(seed)

    seen_keys: set[Any] = set()
    archive: list[WitnessRecord] = []
    total_clones = 0
    round_telemetry: list[dict[str, Any]] = []

    candidate_payloads: list[Any] = []
    initial_keys: set[Any] = set()
    for _ in range(population_size):
        cand = task.random_seed_witness(rng, target_size)
        key = _structural_key(cand)
        for _retry in range(2):
            if key not in initial_keys:
                break
            cand = task.random_seed_witness(rng, target_size)
            key = _structural_key(cand)
        initial_keys.add(key)
        candidate_payloads.append(cand)

    elites: list[WitnessRecord] = []
    for round_idx in range(rounds):
        unique_added = 0
        clones_in_round = 0

        for seed_payload in candidate_payloads:
            refined = task.local_refine(seed_payload, rng, local_steps)
            key = _structural_key(refined)
            if key in seen_keys:
                clones_in_round += 1
                total_clones += 1
                continue
            seen_keys.add(key)
            feasible, energy, objective, descriptor = task.verify_witness(refined)
            archive.append(
                WitnessRecord(
                    payload=refined,
                    feasible=bool(feasible),
                    energy=energy,
                    objective=objective,
                    descriptor=descriptor,
                    round_idx=round_idx,
                )
            )
            unique_added += 1

        archive.sort(key=_record_sort_key)
        elites = archive[:effective_elite_k]
        best = archive[0]

        round_telemetry.append(
            {
                "round": round_idx,
                "candidates_evaluated": len(candidate_payloads),
                "unique_added": unique_added,
                "deduplicated_clones": clones_in_round,
                "archive_size": len(archive),
                "best_feasible": best.feasible,
                "best_energy": best.energy,
                "best_objective": best.objective,
                "elite_energies": [e.energy for e in elites],
                "elite_objectives": [e.objective for e in elites],
            }
        )

        if round_idx + 1 < rounds:
            next_payloads: list[Any] = []
            batch_keys: set[Any] = set()

            if population_size >= 2:
                top_payload = elites[0].payload
                next_payloads.append(top_payload)
                batch_keys.add(_structural_key(top_payload))

            fresh_slots = max(1, population_size // 4) if population_size >= 4 else (1 if population_size >= 3 else 0)
            recombine_slots = population_size - len(next_payloads) - fresh_slots

            for _ in range(recombine_slots):
                child = task.recombine(elites, rng, round_idx)
                child_key = _structural_key(child)
                for _retry in range(3):
                    if child_key not in batch_keys:
                        break
                    child = task.recombine(elites, rng, round_idx)
                    child_key = _structural_key(child)
                batch_keys.add(child_key)
                next_payloads.append(child)

            for _ in range(fresh_slots):
                fresh = task.random_seed_witness(rng, target_size)
                fresh_key = _structural_key(fresh)
                for _retry in range(2):
                    if fresh_key not in batch_keys and fresh_key not in seen_keys:
                        break
                    fresh = task.random_seed_witness(rng, target_size)
                    fresh_key = _structural_key(fresh)
                batch_keys.add(fresh_key)
                next_payloads.append(fresh)

            candidate_payloads = next_payloads

    best = archive[0]
    return {
        "feasible": best.feasible,
        "best_energy": best.energy,
        "best_objective": best.objective,
        "best_payload": best.payload,
        "best_descriptor": best.descriptor,
        "rounds_completed": rounds,
        "total_unique_witnesses": len(archive),
        "total_deduplicated_clones": total_clones,
        "elites": [
            {
                "feasible": e.feasible,
                "energy": e.energy,
                "objective": e.objective,
                "descriptor": e.descriptor,
                "round_idx": e.round_idx,
            }
            for e in elites
        ],
        "round_telemetry": round_telemetry,
    }
