"""Zeller delta-debugging (ddmin) minimal witness reducer."""
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def _partition_ranges(length: int, chunks: int) -> list[tuple[int, int]]:
    base, extra = divmod(length, chunks)
    ranges: list[tuple[int, int]] = []
    pos = 0
    for idx in range(chunks):
        width = base + (1 if idx < extra else 0)
        if width > 0:
            ranges.append((pos, pos + width))
            pos += width
    return ranges


def ddmin_reduce(
    items: Sequence[T],
    reproduces: Callable[[Sequence[T]], bool],
    *,
    min_size: int = 1,
    max_probes: int = 24,
) -> list[T]:
    """Minimize ``items`` while preserving ``reproduces(candidate)`` within ``max_probes`` calls."""
    if type(min_size) is not int or min_size < 0:
        raise ValueError("min_size must be a nonnegative integer")
    if type(max_probes) is not int or max_probes < 1:
        raise ValueError("max_probes must be an integer >= 1")

    cur = list(items)
    probes = 1
    if not reproduces(cur):
        raise ValueError("Initial items do not satisfy reproduces predicate")

    if len(cur) <= min_size or probes >= max_probes:
        return cur

    n = 2
    while len(cur) > min_size and probes < max_probes:
        granularity = min(n, len(cur))
        ranges = _partition_ranges(len(cur), granularity)
        reduced = False

        # Try complements first (remove one chunk at a time).
        for start, end in ranges:
            cand = cur[:start] + cur[end:]
            if len(cand) < min_size:
                continue
            if probes >= max_probes:
                break
            probes += 1
            if reproduces(cand):
                cur = cand
                n = max(granularity - 1, 2)
                reduced = True
                break

        if reduced:
            continue
        if probes >= max_probes:
            break

        # When granularity == 2, subsets coincide with complements already probed.
        if granularity > 2:
            for start, end in ranges:
                cand = cur[start:end]
                if len(cand) < min_size:
                    continue
                if probes >= max_probes:
                    break
                probes += 1
                if reproduces(cand):
                    cur = cand
                    n = 2
                    reduced = True
                    break

        if reduced:
            continue
        if probes >= max_probes or granularity >= len(cur):
            break
        n = min(len(cur), granularity * 2)

    return cur
