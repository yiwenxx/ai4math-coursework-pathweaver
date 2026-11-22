"""Capacity-aware matching with full-DAG path guidance, without reference input.

Matching costs only propose assignments. Incumbents are compared by exact (T,L).
The verifier remains independent and recomputes coordinates, capacity and paths.
"""
from collections import deque
from dataclasses import dataclass
from random import Random
from time import monotonic
from typing import Any, Mapping

from pathweaver.core.contracts import SolveBudget
from .model import SCHEMA_VERSION, TASK_ID, geometric_length, parse_instance


STRATEGY_NAME = "path_guided_min_cost_matching_v2"


class _Deadline(Exception):
    pass


def _check(deadline):
    if monotonic() >= deadline:
        raise _Deadline


@dataclass(frozen=True)
class _Matching:
    columns: list[int]
    row_potentials: list[int]
    site_potentials: list[int]


def _hungarian(costs, deadline):
    """Minimum-cost injection for a rectangular integer matrix (rows <= columns).

Forbidden entries are supplied with a finite dominating cost and checked by the
caller afterwards. Potentials and reduced costs use exact Python integers.
"""
    n = len(costs)
    if not n:
        return _Matching([], [], [])
    m = len(costs[0])
    if n > m:
        return None
    u, v, owner = [0] * (n + 1), [0] * (m + 1), [0] * (m + 1)
    for row in range(1, n + 1):
        _check(deadline)
        owner[0] = row
        column = 0
        slack, previous, used = [None] * (m + 1), [0] * (m + 1), [False] * (m + 1)
        while True:
            _check(deadline)
            used[column] = True
            current = owner[column]
            delta, next_column = None, 0
            values = costs[current - 1]
            for j in range(1, m + 1):
                if used[j]:
                    continue
                reduced = values[j - 1] - u[current] - v[j]
                if slack[j] is None or reduced < slack[j]:
                    slack[j], previous[j] = reduced, column
                if delta is None or slack[j] < delta:
                    delta, next_column = slack[j], j
            for j in range(m + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                elif slack[j] is not None:
                    slack[j] -= delta
            column = next_column
            if owner[column] == 0:
                break
        while column:
            before = previous[column]
            owner[column] = owner[before]
            column = before
    answer = [0] * n
    for column in range(1, m + 1):
        if owner[column]:
            answer[owner[column] - 1] = column - 1
    return _Matching(answer, u[1:], v[1:])


@dataclass
class _State:
    objectives: tuple[int, int]
    arrivals: list[int]
    remaining: list[int]
    delays: list[int]


class _Graph:
    """Cache topology and geometric lengths; recompute every DAG path per score."""

    def __init__(self, instance):
        self.instance = instance
        self.edges = instance.edges
        index = {node: i for i, node in enumerate(instance.topological_order)}
        self.source = [index[e.source] for e in self.edges]
        self.target = [index[e.target] for e in self.edges]
        self.outgoing = [[] for _ in index]
        self.cross, self.lengths = [], {}
        for i, edge in enumerate(self.edges):
            self.outgoing[self.source[i]].append((i, self.target[i]))
            if edge.delay is None:
                self.cross.append(i)
                self.lengths[i] = {s: geometric_length(instance, edge, s) for s in edge.eligible_sites}

    def score(self, assignment=None):
        """None denotes the capacity-relaxed lower bound, also charged one pass."""
        delays = [edge.delay for edge in self.edges]
        total = 0
        for i in self.cross:
            edge = self.edges[i]
            length = (min(self.lengths[i].values()) if assignment is None
                      else self.lengths[i][assignment[edge.id]])
            total += length
            delays[i] = edge.base_delay + edge.alpha * length
        arrival = [0] * len(self.outgoing)
        for node, arcs in enumerate(self.outgoing):
            value = arrival[node]
            for edge, target in arcs:
                candidate = value + delays[edge]
                if candidate > arrival[target]:
                    arrival[target] = candidate
        remaining = [0] * len(self.outgoing)
        for node in range(len(self.outgoing) - 1, -1, -1):
            remaining[node] = max((delays[e] + remaining[v] for e, v in self.outgoing[node]), default=0)
        return _State((max(arrival), total), arrival, remaining, delays)


def solve(instance: Mapping[str, Any], budget: SolveBudget) -> Mapping[str, Any]:
    """Solve from instance data only; parsing and all matching count toward time."""
    started = monotonic()
    deadline = started + budget.wall_seconds
    evaluations, matchings = 0, 0
    best_assignment = best_state = bound = None
    certificate = last_dual = None
    trace, seen = [], set()
    termination = "proposal_stagnation"
    try:
        parsed = parse_instance(instance)
        _check(deadline)
        graph = _Graph(parsed)
        # Singleton sites are globally reserved, including other tier pairs.
        forced = {graph.edges[i].id: graph.edges[i].eligible_sites[0]
                  for i in graph.cross if len(graph.edges[i].eligible_sites) == 1}
        reserved = set(forced.values())
        movable = [i for i in graph.cross if graph.edges[i].id not in forced]
        sites = sorted({s for i in movable for s in graph.lengths[i] if s not in reserved})
        rng = Random(budget.seed)
        rng.shuffle(movable)
        rng.shuffle(sites)
        site_index = {s: j for j, s in enumerate(sites)}
        domains = [{site_index[s]: length for s, length in graph.lengths[i].items()
                    if s in site_index} for i in movable]

        def reason():
            if monotonic() >= deadline:
                return "wall_budget"
            if evaluations >= budget.max_evaluations:
                return "evaluation_budget"
            return None

        def matching(caps=None, weights=None):
            nonlocal matchings, last_dual
            matrix_rows = []
            for row, i in enumerate(movable):
                _check(deadline)
                edge = graph.edges[i]
                allowed = {j: length * (weights[row] if weights else 1)
                           for j, length in domains[row].items()
                           if caps is None or edge.base_delay + edge.alpha * length <= caps[row]}
                if not allowed:
                    return None
                matrix_rows.append(allowed)
            # Any feasible total is strictly smaller than this forbidden entry.
            forbidden = 1 + sum(max(row.values()) for row in matrix_rows)
            matrix = [[row.get(j, forbidden) for j in range(len(sites))] for row in matrix_rows]
            result = _hungarian(matrix, deadline)
            matchings += 1
            if result is None or any(j not in matrix_rows[row] for row, j in enumerate(result.columns)):
                return None
            last_dual = result
            return {**forced, **{graph.edges[i].id: sites[result.columns[row]]
                                for row, i in enumerate(movable)}}

        def consider(assignment, phase):
            nonlocal evaluations, best_assignment, best_state
            if assignment is None or reason():
                return None
            signature = tuple(assignment[graph.edges[i].id] for i in movable)
            if signature in seen:
                return None
            seen.add(signature)
            state = graph.score(assignment)
            evaluations += 1
            improved = best_state is None or state.objectives < best_state.objectives
            if improved:
                best_assignment, best_state = assignment, state
            trace.append({"evaluation": evaluations, "phase": phase,
                          "objectives": list(state.objectives), "accepted": improved,
                          "elapsed_seconds": monotonic() - started})
            return state

        def find_hall_conflict(threshold):
            """Find a subset of movable rows whose allowed neighborhood at <= threshold violates Hall's theorem."""
            adj = []
            for row, i in enumerate(movable):
                edge = graph.edges[i]
                cap = threshold - bound.arrivals[graph.source[i]] - bound.remaining[graph.target[i]]
                adj.append([
                    j for j, length in domains[row].items()
                    if edge.base_delay + edge.alpha * length <= cap
                ])
                if not adj[-1]:
                    return [graph.edges[i].id]
            site_owner: dict[int, int] = {}
            row_owner: dict[int, int] = {}
            for r in range(len(movable)):
                _check(deadline)
                visited_rows = {r}
                visited_sites = set()
                queue = deque([r])
                parent_site = {}
                found_site = None
                while queue and found_site is None:
                    cur = queue.popleft()
                    for j in adj[cur]:
                        if j in visited_sites:
                            continue
                        visited_sites.add(j)
                        parent_site[j] = cur
                        if j not in site_owner:
                            found_site = j
                            break
                        nxt = site_owner[j]
                        if nxt not in visited_rows:
                            visited_rows.add(nxt)
                            queue.append(nxt)
                if found_site is None:
                    return [graph.edges[movable[idx]].id for idx in sorted(visited_rows)]
                # Augment along alternating path in O(path length).
                cur_site = found_site
                while cur_site is not None:
                    owner_row = parent_site[cur_site]
                    prev_site = row_owner.get(owner_row)
                    site_owner[cur_site] = owner_row
                    row_owner[owner_row] = cur_site
                    cur_site = prev_site
            return None

        caps = None
        if budget.max_evaluations >= 2:
            _check(deadline)
            bound = graph.score()
            evaluations += 1
            # Necessary, not sufficient: a(u) and r(v) are lower bounds even
            # when several variable edges share a path. Full scoring is required.
            caps = [bound.objectives[0] - bound.arrivals[graph.source[i]]
                    - bound.remaining[graph.target[i]] for i in movable]
        initial = matching(caps)
        restricted_initial = initial is not None and bound is not None
        hall_bound = None
        hall_blocking_set = None
        if initial is None and bound is not None and movable:
            # Binary search smallest threshold T_hall >= T_lb + 1 admitting a complete matching.
            thresholds = sorted({
                bound.arrivals[graph.source[i]] + graph.edges[i].base_delay
                + graph.edges[i].alpha * length + bound.remaining[graph.target[i]]
                for row, i in enumerate(movable)
                for length in domains[row].values()
            })
            candidates = [t for t in thresholds if t > bound.objectives[0]]
            lo, hi = 0, len(candidates) - 1
            best_idx = None
            while lo <= hi:
                mid = (lo + hi) // 2
                _check(deadline)
                if find_hall_conflict(candidates[mid]) is None:
                    best_idx = mid
                    hi = mid - 1
                else:
                    lo = mid + 1
            if best_idx is not None:
                hall_bound = candidates[best_idx]
                hall_blocking_set = find_hall_conflict(hall_bound - 1)
                hall_caps = [hall_bound - bound.arrivals[graph.source[i]]
                             - bound.remaining[graph.target[i]] for i in movable]
                initial = matching(hall_caps)
                if initial is not None:
                    caps = hall_caps
        if initial is None:
            initial = matching()
        if initial is None:
            raise ValueError("minimum-cost matching failed for a validated feasible instance")
        consider(
            initial,
            "minimum_length_under_relaxed_path_caps" if restricted_initial
            else "minimum_length_under_hall_path_caps" if hall_bound is not None
            else "minimum_length",
        )
        if best_state is None:
            raise _Deadline

        if restricted_initial and best_state.objectives[0] == bound.objectives[0]:
            # The initial matching minimizes L over a necessary relaxation of
            # T=T_lb. Feasibility at T_lb closes that search; no extra scores.
            # Independent verification still assigns its own evidence level.
            termination = "matching_minimum_at_path_bound"
            certificate = {
                "schema_version": 1, "method": "relaxed_path_matching_duality",
                "T_lower_bound": bound.objectives[0],
                "row_potentials": {graph.edges[i].id: last_dual.row_potentials[row]
                                   for row, i in enumerate(movable)},
                "site_potentials": {site: last_dual.site_potentials[column]
                                    for column, site in enumerate(sites)},
            }
        elif hall_bound is not None and hall_blocking_set and best_state.objectives[0] == hall_bound:
            termination = "matching_minimum_at_hall_bound"
            certificate = {
                "schema_version": 1, "method": "hall_bottleneck_and_dual",
                "T_lower_bound": hall_bound,
                "hall_blocking_set": hall_blocking_set,
                "row_potentials": {graph.edges[i].id: last_dual.row_potentials[row]
                                   for row, i in enumerate(movable)},
                "site_potentials": {site: last_dual.site_potentials[column]
                                    for column, site in enumerate(sites)},
            }
        else:
            # Multi-edge capacity-preserving proposals respond to the complete
            # current graph, rather than scanning all pairs in seeded order.
            # Their surrogate costs never replace exact incumbent comparison.
            weights = [1] * len(movable)
            working = best_state
            for round_number in range(8):
                if reason():
                    break
                total = working.objectives[0]
                threshold = max(1, total - (bound.objectives[0] if bound else 0))
                for row, i in enumerate(movable):
                    through = (working.arrivals[graph.source[i]] + working.delays[i]
                               + working.remaining[graph.target[i]])
                    slack = total - through
                    if slack < threshold:
                        weights[row] += 1 + (threshold - slack) * 8 // threshold
                candidate = matching(caps if (restricted_initial or hall_bound is not None) else None, weights)
                trial = consider(candidate, f"path_pressure_{round_number + 1}")
                if trial is not None:
                    working = trial
                if bound and best_state.objectives[0] == bound.objectives[0]:
                    break

            # Both earliest arrivals and latest permissible arrivals are feasible
            # vertex potentials for the incumbent. Their integer convex blends
            # remain feasible. Caps P(v)-P(u) therefore preserve the full-DAG T
            # while a global minimum-cost matching improves capacity allocation.
            for numerator in (0, 1, 2):
                if reason():
                    break
                total = best_state.objectives[0]
                potential = [((2 - numerator) * a + numerator * (total - r)) // 2
                             for a, r in zip(best_state.arrivals, best_state.remaining)]
                safe_caps = [potential[graph.target[i]] - potential[graph.source[i]] for i in movable]
                consider(matching(safe_caps), f"feasible_path_potentials_{numerator}/2")
            if certificate is None and hall_bound is not None and hall_blocking_set:
                certificate = {
                    "schema_version": 1, "method": "hall_bottleneck_lower_bound",
                    "T_lower_bound": hall_bound,
                    "hall_blocking_set": hall_blocking_set,
                }
            termination = reason() or "proposal_stagnation"
    except _Deadline:
        termination = "wall_budget"
    if best_assignment is None:
        raise TimeoutError("path-matching strategy exhausted wall budget before its initial score")
    solution = {
        "schema_version": SCHEMA_VERSION, "task_id": TASK_ID,
        "instance_id": parsed.instance_id, "solution": {"assignment": best_assignment},
        "metadata": {
            "baseline": STRATEGY_NAME, "seed": budget.seed, "evaluations": evaluations,
            "bound_evaluations": int(bound is not None),
            "candidate_evaluations": len(trace), "completed_matchings": matchings,
            "termination": termination, "trace": trace,
            "solver_objectives": list(best_state.objectives),
        },
    }
    if certificate is not None:
        solution["optimality_certificate"] = certificate
    return solution
