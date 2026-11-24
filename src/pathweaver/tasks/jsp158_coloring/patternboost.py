"""PatternBoost constructive witness engine for JSP-000158 interval and cyclic 4-AP colorings."""
from collections import Counter
from collections.abc import Sequence
import random
from typing import Any

from pathweaver.core.constructive import WitnessRecord

from .cyclic_sat import count_cyclic_abba_violations, multiplicative_subgroups
from .evaluator import PreparedJsp158Instance, evaluate_prepared, prepare_verifier
from .model import MAX_N, SCHEMA_VERSION, TASK_ID, generate


def _canonicalize_colors(colors: Sequence[int]) -> list[int]:
    remap: dict[int, int] = {}
    return [remap.setdefault(c, len(remap)) for c in colors]


def _align_colors_to_target(source: Sequence[int], target: Sequence[int]) -> list[int]:
    """Greedily align source color labels to target color labels by maximal position overlap."""
    pair_counts: Counter[tuple[int, int]] = Counter(zip(source, target, strict=True))
    src_to_tgt: dict[int, int] = {}
    used_tgt: set[int] = set()
    for (sc, tc), _ in pair_counts.most_common():
        if sc not in src_to_tgt and tc not in used_tgt:
            src_to_tgt[sc] = tc
            used_tgt.add(tc)
    next_label = (max(used_tgt) + 1) if used_tgt else 0
    for sc in source:
        if sc not in src_to_tgt:
            while next_label in used_tgt:
                next_label += 1
            src_to_tgt[sc] = next_label
            used_tgt.add(next_label)
            next_label += 1
    return [src_to_tgt[c] for c in source]


def _cyclic_cosets(m: int, subgroup: tuple[int, ...]) -> list[tuple[int, ...]]:
    seen = [False] * m
    cosets: list[tuple[int, ...]] = []
    for x in range(m):
        if seen[x]:
            continue
        orbit = sorted({(x * h) % m for h in subgroup})
        for y in orbit:
            seen[y] = True
        cosets.append(tuple(orbit))
    return cosets


class Jsp158PatternBoostTask:
    """PatternBoost task adapter for JSP-000158 interval 4-AP and cyclic ABBA colorings."""

    def __init__(
        self,
        mode: str = "interval",
        n: int = 16,
        colors: int | None = None,
    ) -> None:
        if mode not in ("interval", "cyclic"):
            raise ValueError(f"Unsupported PatternBoost mode {mode!r}; expected 'interval' or 'cyclic'")
        if type(n) is not int:
            raise ValueError("n must be an integer")
        if colors is not None and (type(colors) is not int or colors < 1):
            raise ValueError("colors must be a positive integer when provided")

        self.mode = mode
        self.n = n
        self.colors = colors

        if mode == "interval":
            if not (1 <= n <= MAX_N):
                raise ValueError(f"interval n must be in [1, {MAX_N}]")
            self._prepared: PreparedJsp158Instance | None = prepare_verifier(generate(seed=0, size=n))
            self._interval_triples = self._build_interval_triples(self._prepared)
            self._cyclic_aps: tuple[tuple[int, int, int, int], ...] = ()
            self._cyclic_incident: tuple[tuple[int, ...], ...] = ()
            self._cyclic_rules: tuple[tuple[tuple[int, int, int], ...], ...] = ()
            self._subgroups: list[tuple[int, ...]] = []
            self._cyclic_r = colors if colors is not None else min(n, 3)
        else:
            if n < 2:
                raise ValueError("cyclic modulus n must be >= 2")
            self._prepared = None
            self._interval_triples = ()
            self._cyclic_r = colors if colors is not None else min(n, 3)
            aps, incident, rules = self._build_cyclic_tables(n)
            self._cyclic_aps = aps
            self._cyclic_incident = incident
            self._cyclic_rules = rules
            self._subgroups = multiplicative_subgroups(n, avoid_minus_one=True)

    @staticmethod
    def _build_interval_triples(
        prepared: PreparedJsp158Instance,
    ) -> tuple[tuple[tuple[int, int, int], ...], ...]:
        n = prepared.instance.n
        aps = prepared.aps
        triples: list[tuple[tuple[int, int, int], ...]] = []
        for pos in range(n):
            row: list[tuple[int, int, int]] = []
            for ap_idx in prepared.incident[pos]:
                a, b, c, d = aps[ap_idx]
                if pos == a:
                    row.append((b, c, d))
                elif pos == b:
                    row.append((a, c, d))
                elif pos == c:
                    row.append((a, b, d))
                else:
                    row.append((a, b, c))
            triples.append(tuple(row))
        return tuple(triples)

    @staticmethod
    def _build_cyclic_tables(
        m: int,
    ) -> tuple[
        tuple[tuple[int, int, int, int], ...],
        tuple[tuple[int, ...], ...],
        tuple[tuple[tuple[int, int, int], ...], ...],
    ]:
        aps: list[tuple[int, int, int, int]] = []
        incident: list[list[int]] = [[] for _ in range(m)]
        rules: list[list[tuple[int, int, int]]] = [[] for _ in range(m)]

        for a in range(m):
            for d in range(1, m):
                p0 = a
                p1 = (a + d) % m
                p2 = (a + 2 * d) % m
                p3 = (a + 3 * d) % m
                idx = len(aps)
                aps.append((p0, p1, p2, p3))

                positions = {p0, p1, p2, p3}
                for pos in positions:
                    incident[pos].append(idx)

                if p0 == p3:
                    # 3d == 0 mod m: p0 == p3; only inner positions vary the condition.
                    if p1 != p2:
                        rules[p1].append((p2, p2, p2))
                        rules[p2].append((p1, p1, p1))
                elif p0 == p2 and p1 == p3:
                    # 2d == 0 mod m: c(p0) == c(p1) triggers ABBA.
                    rules[p0].append((p1, p1, p1))
                    rules[p1].append((p0, p0, p0))
                else:
                    rules[p0].append((p3, p1, p2))
                    rules[p3].append((p0, p1, p2))
                    rules[p1].append((p2, p0, p3))
                    rules[p2].append((p1, p0, p3))

        return (
            tuple(aps),
            tuple(tuple(row) for row in incident),
            tuple(tuple(row) for row in rules),
        )

    def random_seed_witness(self, rng: random.Random, size: int) -> list[int]:
        del size
        if self.mode == "interval":
            return self._random_interval_seed(rng)
        return self._random_cyclic_seed(rng)

    def _random_interval_seed(self, rng: random.Random) -> list[int]:
        n = self.n
        if self.colors is not None:
            k = min(self.colors, n)
            col = [rng.randrange(k) for _ in range(n)]
            # Quick randomized greedy pass to reduce initial conflicts.
            order = list(range(n))
            rng.shuffle(order)
            counts = [0] * k
            for pos in order[: max(1, n // 2)]:
                for c in range(k):
                    counts[c] = 0
                for o1, o2, o3 in self._interval_triples[pos]:
                    c1, c2, c3 = col[o1], col[o2], col[o3]
                    if c1 == c2 and c2 != c3:
                        counts[c1] += 1
                        counts[c3] += 1
                    elif (c1 == c3 or c2 == c3) and c1 != c2:
                        counts[c1] += 1
                        counts[c2] += 1
                best_val = min(counts)
                cands = [c for c in range(k) if counts[c] == best_val]
                col[pos] = rng.choice(cands)
            return _canonicalize_colors(col)

        # Unbounded k: build a randomized greedy legal 4-AP coloring.
        col = [-1] * n
        order = list(range(n))
        rng.shuffle(order)
        max_k = 0
        for pos in order:
            forbidden: set[int] = set()
            for o1, o2, o3 in self._interval_triples[pos]:
                c1, c2, c3 = col[o1], col[o2], col[o3]
                if c1 < 0 or c2 < 0 or c3 < 0:
                    continue
                if c1 == c2 and c2 == c3:
                    forbidden.add(c1)
                elif c1 == c2:
                    forbidden.add(c1)
                    forbidden.add(c3)
                elif c1 == c3 or c2 == c3:
                    forbidden.add(c1)
                    forbidden.add(c2)
            avail = [c for c in range(max_k) if c not in forbidden]
            if avail:
                # Favor existing colors slightly differently per seed for diversity.
                col[pos] = avail[0] if rng.random() < 0.7 else rng.choice(avail)
            else:
                col[pos] = max_k
                max_k += 1
        return _canonicalize_colors(col)

    def _random_cyclic_seed(self, rng: random.Random) -> list[int]:
        m = self.n
        r = self._cyclic_r
        choice = rng.random()
        if self._subgroups and choice < 0.35:
            sub = rng.choice(self._subgroups)
            cosets = _cyclic_cosets(m, sub)
            col = [0] * m
            for coset in cosets:
                label = rng.randrange(r)
                for x in coset:
                    col[x] = label
            return col
        if choice < 0.60:
            col = [0] * m
            shift = 1 if (r >= 2 and rng.random() < 0.5) else 0
            for x in range(m):
                neg_x = (-x) % m
                if x <= neg_x:
                    c = rng.randrange(r)
                    col[x] = c
                    if neg_x != x:
                        col[neg_x] = (c + shift) % r
            return col
        return [rng.randrange(r) for _ in range(m)]

    def local_refine(self, payload: Any, rng: random.Random, max_steps: int) -> list[int]:
        if self.mode == "interval":
            return self._local_refine_interval(list(payload), rng, max_steps)
        return self._local_refine_cyclic(list(payload), rng, max_steps)

    def _interval_violations(self, col: Sequence[int]) -> tuple[list[int], int]:
        assert self._prepared is not None
        aps = self._prepared.aps
        ap_bad = [0] * len(aps)
        total = 0
        for idx, (a, b, c, d) in enumerate(aps):
            ca, cb, cc, cd = col[a], col[b], col[c], col[d]
            if len({ca, cb, cc, cd}) < 3:
                ap_bad[idx] = 1
                total += 1
        return ap_bad, total

    def _tabu_interval(
        self,
        init_col: list[int],
        k: int,
        rng: random.Random,
        max_steps: int,
    ) -> tuple[list[int], int, int]:
        assert self._prepared is not None
        n = self.n
        aps = self._prepared.aps
        incident = self._prepared.incident
        triples = self._interval_triples
        col = list(init_col)
        ap_bad, total_bad = self._interval_violations(col)

        best_col = list(col)
        best_bad = total_bad
        if total_bad == 0 or max_steps <= 0 or k <= 1:
            return best_col, best_bad, 0

        tabu_until: dict[tuple[int, int], int] = {}
        tenure = max(4, min(18, n // 3 + 3))
        bad_counts = [0] * k
        steps_used = 0

        for step in range(1, max_steps + 1):
            steps_used = step
            if total_bad == 0:
                break

            bad_positions: list[int] = []
            seen_pos = [False] * n
            for ap_idx, flag in enumerate(ap_bad):
                if flag:
                    for p in aps[ap_idx]:
                        if not seen_pos[p]:
                            seen_pos[p] = True
                            bad_positions.append(p)

            sample_size = min(len(bad_positions), max(6, min(16, n)))
            cand_positions = (
                bad_positions if len(bad_positions) <= sample_size else rng.sample(bad_positions, sample_size)
            )

            best_move: tuple[int, int, int] | None = None  # (new_total, pos, new_c)
            best_ties: list[tuple[int, int, int]] = []

            for pos in cand_positions:
                old_c = col[pos]
                for c in range(k):
                    bad_counts[c] = 0
                for o1, o2, o3 in triples[pos]:
                    c1, c2, c3 = col[o1], col[o2], col[o3]
                    if c1 == c2:
                        if c2 != c3:
                            bad_counts[c1] += 1
                            bad_counts[c3] += 1
                    elif c1 == c3 or c2 == c3:
                        bad_counts[c1] += 1
                        bad_counts[c2] += 1

                cur_bad = bad_counts[old_c]
                for cand_c in range(k):
                    if cand_c == old_c:
                        continue
                    new_total = total_bad - cur_bad + bad_counts[cand_c]
                    is_tabu = tabu_until.get((pos, cand_c), 0) > step
                    if is_tabu and new_total >= best_bad:
                        continue
                    if best_move is None or new_total < best_move[0]:
                        best_move = (new_total, pos, cand_c)
                        best_ties = [best_move]
                    elif new_total == best_move[0]:
                        best_ties.append((new_total, pos, cand_c))

            if not best_ties:
                pos = rng.choice(bad_positions)
                old_c = col[pos]
                cand_c = (old_c + 1 + rng.randrange(k - 1)) % k
                # Recompute exact new_total for fallback move.
                for c in range(k):
                    bad_counts[c] = 0
                for o1, o2, o3 in triples[pos]:
                    c1, c2, c3 = col[o1], col[o2], col[o3]
                    if c1 == c2 and c2 != c3:
                        bad_counts[c1] += 1
                        bad_counts[c3] += 1
                    elif (c1 == c3 or c2 == c3) and c1 != c2:
                        bad_counts[c1] += 1
                        bad_counts[c2] += 1
                new_total = total_bad - bad_counts[old_c] + bad_counts[cand_c]
            else:
                new_total, pos, cand_c = rng.choice(best_ties)

            old_c = col[pos]
            col[pos] = cand_c
            tabu_until[(pos, old_c)] = step + tenure + rng.randint(0, 3)
            for ap_idx in incident[pos]:
                a, b, c, d = aps[ap_idx]
                new_flag = 1 if len({col[a], col[b], col[c], col[d]}) < 3 else 0
                if new_flag != ap_bad[ap_idx]:
                    total_bad += new_flag - ap_bad[ap_idx]
                    ap_bad[ap_idx] = new_flag

            if total_bad < best_bad:
                best_bad = total_bad
                best_col = list(col)

        return best_col, best_bad, steps_used

    def _local_refine_interval(self, col: list[int], rng: random.Random, max_steps: int) -> list[int]:
        if self.n <= 3:
            return [0] * self.n

        if self.colors is not None:
            k = min(self.colors, self.n)
            clamped = [c % k for c in col]
            refined, _, _ = self._tabu_interval(clamped, k, rng, max_steps)
            return _canonicalize_colors(refined)

        # Free color minimization: first reach 0 violations, then iteratively eliminate rare color classes.
        cur = _canonicalize_colors(col)
        cur_k = max(cur) + 1
        refined, bad, steps_used = self._tabu_interval(cur, cur_k, rng, max_steps)
        if bad > 0:
            return _canonicalize_colors(refined)

        best_feasible = _canonicalize_colors(refined)
        remaining_steps = max_steps - steps_used
        triples = self._interval_triples

        while remaining_steps > 0:
            cur_k = max(best_feasible) + 1
            if cur_k <= 3:
                break
            counts = Counter(best_feasible)
            min_freq = min(counts.values())
            rare_colors = [c for c, cnt in counts.items() if cnt == min_freq]
            victim = rng.choice(rare_colors)

            # Drop victim class by greedily reassigning its vertices into remaining colors [0..cur_k-2].
            remap = {}
            nxt = 0
            for c in range(cur_k):
                if c != victim:
                    remap[c] = nxt
                    nxt += 1
            reduced_k = cur_k - 1
            trial = [remap[c] if c != victim else rng.randrange(reduced_k) for c in best_feasible]
            victim_positions = [i for i, c in enumerate(best_feasible) if c == victim]
            rng.shuffle(victim_positions)
            bad_counts = [0] * reduced_k
            for pos in victim_positions:
                for c in range(reduced_k):
                    bad_counts[c] = 0
                for o1, o2, o3 in triples[pos]:
                    c1, c2, c3 = trial[o1], trial[o2], trial[o3]
                    if c1 == c2 and c2 != c3:
                        bad_counts[c1] += 1
                        bad_counts[c3] += 1
                    elif (c1 == c3 or c2 == c3) and c1 != c2:
                        bad_counts[c1] += 1
                        bad_counts[c2] += 1
                best_val = min(bad_counts)
                cands = [c for c in range(reduced_k) if bad_counts[c] == best_val]
                trial[pos] = rng.choice(cands)

            budget_slice = remaining_steps
            candidate, cand_bad, used = self._tabu_interval(trial, reduced_k, rng, budget_slice)
            remaining_steps -= max(1, used)
            if cand_bad == 0:
                best_feasible = _canonicalize_colors(candidate)
            else:
                break

        return best_feasible

    def _local_refine_cyclic(self, col: list[int], rng: random.Random, max_steps: int) -> list[int]:
        m = self.n
        r = self._cyclic_r
        cur = [c % r for c in col]
        aps = self._cyclic_aps
        incident = self._cyclic_incident
        rules = self._cyclic_rules

        ap_bad = [
            1 if (cur[p0] == cur[p3] and cur[p1] == cur[p2]) else 0
            for p0, p1, p2, p3 in aps
        ]
        total_bad = sum(ap_bad)
        best_col = list(cur)
        best_bad = total_bad

        if total_bad == 0 or max_steps <= 0 or r <= 1:
            return best_col

        tabu_until: dict[tuple[int, int], int] = {}
        tenure = max(4, min(16, m // 3 + 3))
        bad_counts = [0] * r

        for step in range(1, max_steps + 1):
            if total_bad == 0:
                break

            bad_positions: list[int] = []
            seen_pos = [False] * m
            for ap_idx, flag in enumerate(ap_bad):
                if flag:
                    for p in aps[ap_idx]:
                        if not seen_pos[p]:
                            seen_pos[p] = True
                            bad_positions.append(p)

            sample_size = min(len(bad_positions), max(6, min(18, m)))
            cand_positions = (
                bad_positions if len(bad_positions) <= sample_size else rng.sample(bad_positions, sample_size)
            )

            best_move: tuple[int, int, int] | None = None
            best_ties: list[tuple[int, int, int]] = []

            for pos in cand_positions:
                old_c = cur[pos]
                for c in range(r):
                    bad_counts[c] = 0
                for partner, q1, q2 in rules[pos]:
                    if cur[q1] == cur[q2]:
                        bad_counts[cur[partner]] += 1
                cur_bad = bad_counts[old_c]

                for cand_c in range(r):
                    if cand_c == old_c:
                        continue
                    new_total = total_bad - cur_bad + bad_counts[cand_c]
                    is_tabu = tabu_until.get((pos, cand_c), 0) > step
                    if is_tabu and new_total >= best_bad:
                        continue
                    if best_move is None or new_total < best_move[0]:
                        best_move = (new_total, pos, cand_c)
                        best_ties = [best_move]
                    elif new_total == best_move[0]:
                        best_ties.append((new_total, pos, cand_c))

            if not best_ties:
                pos = rng.choice(bad_positions)
                old_c = cur[pos]
                cand_c = (old_c + 1 + rng.randrange(r - 1)) % r
            else:
                _, pos, cand_c = rng.choice(best_ties)

            old_c = cur[pos]
            cur[pos] = cand_c
            tabu_until[(pos, old_c)] = step + tenure + rng.randint(0, 3)

            for ap_idx in incident[pos]:
                p0, p1, p2, p3 = aps[ap_idx]
                new_flag = 1 if (cur[p0] == cur[p3] and cur[p1] == cur[p2]) else 0
                if new_flag != ap_bad[ap_idx]:
                    total_bad += new_flag - ap_bad[ap_idx]
                    ap_bad[ap_idx] = new_flag

            if total_bad < best_bad:
                best_bad = total_bad
                best_col = list(cur)

        return best_col

    def recombine(self, elites: Sequence[WitnessRecord], rng: random.Random, round_idx: int) -> list[int]:
        del round_idx
        payloads = [list(e.payload if isinstance(e, WitnessRecord) else e) for e in elites]
        if not payloads:
            return self.random_seed_witness(rng, self.n)
        if self.mode == "interval":
            return self._recombine_interval(payloads, rng)
        return self._recombine_cyclic(payloads, rng)

    def _recombine_interval(self, payloads: list[list[int]], rng: random.Random) -> list[int]:
        n = self.n
        anchor = payloads[0]
        aligned = [anchor] + [_align_colors_to_target(p, anchor) for p in payloads[1:]]
        p1 = rng.choice(aligned)
        p2 = rng.choice(aligned) if len(aligned) == 1 else rng.choice([p for p in aligned if p is not p1] or aligned)

        mode_pick = rng.random()
        if mode_pick < 0.40:
            # Contiguous block motif splicing.
            cut_a = rng.randrange(n)
            cut_b = rng.randrange(n)
            lo, hi = (cut_a, cut_b) if cut_a <= cut_b else (cut_b, cut_a)
            child = [p1[i] if lo <= i <= hi else p2[i] for i in range(n)]
        elif mode_pick < 0.70:
            # Arithmetic-slice recombination respecting AP stride motifs.
            stride = rng.randint(2, max(2, min(7, n)))
            rem = rng.randrange(stride)
            child = [p1[i] if (i % stride) == rem else p2[i] for i in range(n)]
        else:
            # Elite frequency / consensus extraction + mild diversification.
            child = []
            for i in range(n):
                freq = Counter(p[i] for p in aligned)
                top_color, top_cnt = freq.most_common(1)[0]
                if top_cnt * 2 >= len(aligned) and rng.random() < 0.85:
                    child.append(top_color)
                else:
                    child.append(rng.choice(aligned)[i])

        palette_limit = self.colors if self.colors is not None else max(max(child) + 1, 1)
        if palette_limit > 1 and rng.random() < 0.5:
            mut_count = max(1, n // 16)
            for pos in rng.sample(range(n), min(n, mut_count)):
                child[pos] = rng.randrange(palette_limit)

        if self.colors is not None:
            child = [c % self.colors for c in child]
        return _canonicalize_colors(child)

    def _recombine_cyclic(self, payloads: list[list[int]], rng: random.Random) -> list[int]:
        m = self.n
        r = self._cyclic_r
        anchor = payloads[0]

        def transform(seq: list[int]) -> list[int]:
            shift = rng.randrange(m)
            reflect = rng.random() < 0.5
            transformed = [seq[((-x if reflect else x) + shift) % m] for x in range(m)]
            return _align_colors_to_target(transformed, anchor)

        p1 = list(anchor)
        p2 = transform(rng.choice(payloads))
        child = list(p1)

        if self._subgroups and rng.random() < 0.55:
            sub = rng.choice(self._subgroups)
            cosets = _cyclic_cosets(m, sub)
            for coset in cosets:
                pick = rng.random()
                if pick < 0.45:
                    for x in coset:
                        child[x] = p2[x]
                elif pick < 0.65:
                    # Enforce coset-constant motif extracted by majority color on coset.
                    majority = Counter(p1[x] for x in coset).most_common(1)[0][0]
                    for x in coset:
                        child[x] = majority
        elif rng.random() < 0.65:
            # Mirror-symmetric pair recombination on {x, -x mod m}.
            for x in range(m):
                neg_x = (-x) % m
                if x <= neg_x and rng.random() < 0.5:
                    child[x] = p2[x]
                    child[neg_x] = p2[neg_x]
        else:
            # Cyclic arc crossover + elite consensus.
            start = rng.randrange(m)
            width = rng.randint(1, max(1, m // 2))
            for offset in range(width):
                idx = (start + offset) % m
                child[idx] = p2[idx]

        if r > 1 and rng.random() < 0.7:
            mut_count = max(1, m // 12)
            for pos in rng.sample(range(m), min(m, mut_count)):
                child[pos] = rng.randrange(r)

        return [c % r for c in child]

    def verify_witness(self, payload: Any) -> tuple[bool, int, int, dict[str, Any]]:
        if self.mode == "interval":
            assert self._prepared is not None
            colors = [int(c) for c in payload]
            envelope = {
                "schema_version": SCHEMA_VERSION,
                "task_id": TASK_ID,
                "instance_id": self._prepared.instance.instance_id,
                "solution": {"colors": colors},
            }
            ev = evaluate_prepared(self._prepared, envelope)
            violations = int(ev.diagnostics.get("violation_count", 0 if ev.feasible else self.n))
            color_count = int(ev.diagnostics.get("color_count", len(set(colors))))
            return (
                bool(ev.feasible),
                violations,
                color_count,
                {
                    "mode": "interval",
                    "n": self.n,
                    "color_count": color_count,
                    "violation_count": violations,
                    "evidence": ev.evidence.value,
                },
            )

        colors = [int(c) for c in payload]
        if len(colors) != self.n or any(not (0 <= c < self._cyclic_r) for c in colors):
            return (
                False,
                self.n * self.n,
                self._cyclic_r,
                {"mode": "cyclic", "m": self.n, "r": self._cyclic_r, "error": "invalid cyclic colors"},
            )
        violations = count_cyclic_abba_violations(self.n, colors)
        used_colors = len(set(colors))
        return (
            violations == 0,
            violations,
            used_colors,
            {
                "mode": "cyclic",
                "m": self.n,
                "r": self._cyclic_r,
                "violations": violations,
                "used_colors": used_colors,
            },
        )
