"""Color a finite interval using mixed-radix low digits and a finite top word."""

import argparse
from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
import json
import sys


def _dense(word):
    labels = {}
    return tuple(labels.setdefault(value, len(labels)) for value in word)


# The only bad modular progression has residues 5, 19, 33, 0 in that order.
NEAR_47 = tuple(map(int, "40057736833724280244053132762165671734186658548"))
CYCLE_45 = tuple(map(int, "325441522868253137784753427160408506670630811"))
WORDS = {
    7: (0, 1, 2, 1, 3, 3, 2),
    45: _dense(CYCLE_45),
    47: _dense((9,) + NEAR_47[1:]),
    71: _dense(pow(x, 7, 71) for x in range(71)),
    443: _dense(pow(x, 17, 443) if x else 1 for x in range(443)),
}
# (power, primitive root). Zero has the same label as the power value one.
POWER_RULES = {
    3217: (67, 5), 13553: (121, 3), 19603: (121, 2),
    21727: (213, 3), 26497: (207, 5), 648019: (1251, 2),
    817237: (1269, 2), 882751: (1375, 11),
    578743129: (50343, 7),
}
PALETTES = {base: max(word) + 1 for base, word in WORDS.items()}
PALETTES.update({p: (p - 1) // h for p, (h, _) in POWER_RULES.items()})
BOUNDED_DIGITS = {
    # Two base-45 digits (2025 residues, 81 colors) are dominated by base 3217 (48 colors).
    7: 1, 45: 1, 47: 1, 71: 1, 443: 1, 19603: 0, 13553: 0,
    3217: 4, 26497: 3, 648019: 3, 817237: 0, 882751: 5,
    578743129: 46,  # 95 digits of base 21727 dominate 47 of this base.
}
REPEATED_BASE = 21727
DIGIT_BASES = (*BOUNDED_DIGITS, REPEATED_BASE)


@lru_cache(maxsize=None)
def _power_labels(p):
    h, generator = POWER_RULES[p]
    step = pow(generator, h, p)
    value = 1
    image = []
    for _ in range(PALETTES[p]):
        image.append(value)
        value = value * step % p
    return {value: i for i, value in enumerate(sorted(image))}


@lru_cache(maxsize=1)
def _bounded_layouts():
    frontier = [((), 1, 1)]
    for base, limit in BOUNDED_DIGITS.items():
        # A dominated partial layout stays dominated after appending the same
        # digits. Retain just the nondominated products between successive bases.
        powers = [(n, base**n, PALETTES[base]**n) for n in range(limit + 1)]
        candidates = [(palette * colors, -period * capacity, counts + (n,))
                      for counts, period, palette in frontier for n, capacity, colors in powers]
        frontier = []
        for palette, negative_period, counts in sorted(candidates):
            period = -negative_period
            if not frontier or period > frontier[-1][1]:
                frontier.append((counts, period, palette))
    return frontier


@dataclass(frozen=True)
class Tail:
    source: str
    offset: int
    word: tuple
    palette: int


@lru_cache(maxsize=1)
def _tail_menu():
    # These finite words can be used only above the cyclic digits.
    canli77 = "11621104463534521203342250566043463151352021104225456604146315040331262162520"
    repaired98 = (
        "0554041163505723766300211544724267655430352670377"
        "0114626122542433505341154160754036771276260027374"
    )
    changes137 = {0: 0, 1: 1, 6: 5, 7: 0, 135: 5, 136: 6}
    repaired137 = tuple(changes137.get(i, CYCLE_45[(31*i+23) % 45]) for i in range(137))
    tails = [
        Tail("constant", 0, (0,) * 3, 1),
        Tail("interval12", 0, (0, 0, 1, 2, 1, 0, 2, 1, 0, 1, 2, 2), 3),
        Tail("interval77", 0, _dense(map(int, canli77)), 7),
        Tail("interval98", 0, _dense(map(int, repaired98)), 8),
        Tail("interval137", 0, repaired137, 9),
        Tail("near47-step42", 42, _dense(NEAR_47[(42 * x + 42) % 47] for x in range(93)), 9),
    ]
    for base in WORDS:
        word = WORDS[base]
        palette = max(word) + 1
        tails.append(Tail(str(base), 0, word * 3, palette))
        positions = [[] for _ in range(palette)]
        for index, color in enumerate(word):
            positions[color].append(index)
        for group in positions:
            group.append(group[0] + base)
        longest = [(0, 0)] * palette
        for offset in range(base):
            # The (r+1)st distinct color first appears just beyond the r-color window.
            distances = sorted(group[bisect_left(group, offset)] - offset for group in positions)
            for count in range(1, palette):
                length = distances[count]
                if length > longest[count][0]:
                    longest[count] = length, offset
        for count in range(1, palette):
            length, offset = longest[count]
            window = _dense(word[(offset + i) % base] for i in range(length))
            tails.append(Tail(str(base), offset, window, count))

    frontier = []
    for tail in sorted(tails, key=lambda t: (t.palette, -len(t.word))):
        if not frontier or len(tail.word) > len(frontier[-1].word):
            frontier.append(tail)
    return tuple(frontier)


def _covering_exponent(size):
    """Least e with REPEATED_BASE**e >= size, using integer comparisons."""
    bits = REPEATED_BASE.bit_length() - 1
    low, high = 0, (size.bit_length() + bits - 1) // bits
    while low < high:
        mid = (low + high) // 2
        if REPEATED_BASE**mid < size:
            low = mid + 1
        else:
            high = mid
    return low


CRITICAL_PRIME = 578743129
CRITICAL_POWER = POWER_RULES[CRITICAL_PRIME][0]
CRITICAL_COLORS = PALETTES[CRITICAL_PRIME]


def _prefix_power_classes(count):
    # Once a direct listing would exceed the palette size, mark the whole
    # palette. This keeps both time and storage independent of the interval.
    if count >= CRITICAL_COLORS:
        return _power_labels(CRITICAL_PRIME)
    marks = {}
    for x in range(1, count + 1):
        marks.setdefault(pow(x, CRITICAL_POWER, CRITICAL_PRIME), len(marks))
    return marks


class PowerBoundary:
    """Use independent palettes on the columns of the critical two-digit template."""

    def __init__(self, size):
        p, r = CRITICAL_PRIME, CRITICAL_COLORS
        self.rows, self.remainder = divmod(size - 3 * p * p, p)
        self.upper = _prefix_power_classes(max(0, self.rows - 1))
        self.next_power = pow(self.rows, CRITICAL_POWER, p) if self.rows else None
        self.lower = {}
        if self.rows and self.next_power not in self.upper:
            self.lower = _prefix_power_classes(max(0, self.remainder - 1))
        self.base_palette = r * (r + 2 * len(self.upper))
        self.palette = self.base_palette + 2 * len(self.lower)
        if not self.rows or self.next_power in self.upper or len(self.lower) == r:
            self.capacity = min(4 * p * p, p * (3 * p + self.rows + 1) + 1)
        else:
            self.capacity = p * (3 * p + self.rows) + max(1, self.remainder)

    def color(self, n):
        p, r = CRITICAL_PRIME, CRITICAL_COLORS
        quotient, x = divmod(n, p)
        layer, y = divmod(quotient, p)
        labels = _power_labels(p)
        upper_power = pow(y, CRITICAL_POWER, p) if y else 1
        if x == 0:
            # This entire column may use any of the global colors. Its own
            # conditional step p is handled by the four-letter word 0012.
            return labels[upper_power] + r * (0, 0, 1, 2)[layer]
        lower_power = pow(x, CRITICAL_POWER, p)
        low_label = labels[lower_power]
        if y == 0:
            return low_label + r * (layer % 3)
        if layer in (1, 2):
            if upper_power in self.upper:
                return low_label + r * (r + 2 * self.upper[upper_power] + layer - 1)
            if upper_power == self.next_power and lower_power in self.lower:
                return self.base_palette + 2 * self.lower[lower_power] + layer - 1
        return low_label + r * labels[upper_power]


class CyclicProductColoring:
    def __init__(self, size):
        if type(size) is not int or size < 1:
            raise ValueError("the interval size must be a positive integer")
        self.size = size
        tails = _tail_menu()
        widths = [len(tail.word) for tail in tails]
        # Larger counts admit the strict replacements proved in the finite-product note.
        small = _bounded_layouts()
        max_extra = small[-1][1] * widths[-1]
        c = _covering_exponent(size)
        large_period, large_palette = REPEATED_BASE**c, PALETTES[REPEATED_BASE]**c
        best = None
        while large_period * max_extra >= size:
            needed = (size + large_period - 1) // large_period
            for counts, small_period, small_palette in small:
                tail_width = (needed + small_period - 1) // small_period
                index = bisect_left(widths, tail_width)
                if index == len(tails):
                    continue
                tail = tails[index]
                palette = large_palette * small_palette * tail.palette
                capacity = large_period * small_period * len(tail.word)
                key = (palette, tail.palette, -capacity, counts, c)
                if best is None or key < best:
                    best = key
                    self.counts = (*counts, c)
                    self.period = large_period * small_period
                    self.tail = tail
                    self.palette = palette
            if c == 0:
                break
            c -= 1
            large_period //= REPEATED_BASE
            large_palette //= PALETTES[REPEATED_BASE]

        self.boundary = None
        p = CRITICAL_PRIME
        if 3 * p * p < size <= 4 * p * p:
            candidate = PowerBoundary(size)
            if candidate.palette < self.palette:
                self.boundary = candidate
                self.palette = candidate.palette
                self.period = p * p
                self.counts = tuple(2 if base == p else 0 for base in DIGIT_BASES)
                self.tail = None

    def budget(self):
        if self.boundary is not None:
            return {
                "interval_size": self.size,
                "construction": "power_boundary",
                "low_digit_counts": dict(zip(DIGIT_BASES, self.counts)),
                "low_period": self.period,
                "tail_source": "zero_column_and_marked_power_classes",
                "tail_offset": None,
                "tail_length": None,
                "tail_palette": None,
                "complete_extra_rows": self.boundary.rows,
                "partial_row_length": self.boundary.remainder,
                "marked_upper_colors": len(self.boundary.upper),
                "marked_lower_colors": len(self.boundary.lower),
                "capacity": self.boundary.capacity,
                "palette_bound": self.palette,
            }
        return {
            "interval_size": self.size,
            "low_digit_counts": dict(zip(DIGIT_BASES, self.counts)),
            "low_period": self.period,
            "tail_source": self.tail.source,
            "tail_offset": self.tail.offset,
            "tail_length": len(self.tail.word),
            "tail_palette": self.tail.palette,
            "capacity": self.period * len(self.tail.word),
            "palette_bound": self.palette,
        }

    def color(self, x):
        if type(x) is not int or not 0 <= x < self.size:
            raise ValueError("the representative must lie in [0, N)")
        if self.boundary is not None:
            return self.boundary.color(x)
        code, weight = 0, 1
        for base, count in zip(DIGIT_BASES, self.counts):
            for _ in range(count):
                if x == 0:
                    return code  # All remaining zero digits have label zero, including the tail.
                x, digit = divmod(x, base)
                if base in WORDS:
                    label = WORDS[base][digit]
                else:
                    power = pow(digit, POWER_RULES[base][0], base) if digit else 1
                    label = _power_labels(base)[power]
                code += weight * label
                weight *= PALETTES[base]
        return code + weight * self.tail.word[x]


if __name__ == "__main__":
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval-size", type=int, required=True, metavar="N")
    parser.add_argument("x", type=int, nargs="?", help="zero-based representative")
    parser.add_argument("--budget", action="store_true", help="show the chosen layout and palette bound")
    args = parser.parse_args()
    if args.budget == (args.x is not None):
        parser.error("supply either x or --budget")
    try:
        coloring = CyclicProductColoring(args.interval_size)
        print(json.dumps(coloring.budget() if args.budget else coloring.color(args.x)))
    except ValueError as error:
        parser.error(str(error))
