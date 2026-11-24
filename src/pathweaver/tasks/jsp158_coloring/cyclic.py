"""Exhaustive checks of ordinary and set-valued cyclic progression templates."""
from typing import Any


MAX_TEMPLATE_SIZE = 4096
MAX_ORDINARY_THREE_COLOR_SIZE = 8192
MAX_TEMPLATE_BYTES = 1_048_576


def parse_template(template: Any, *, three_colors: bool = False) -> tuple[list[frozenset[int]], int, int]:
    """Return the sets of labels, size of their union, and minimum width."""
    if not isinstance(template, dict) or template.keys() not in ({"colors"}, {"palettes"}):
        raise ValueError("expected exactly one array, colors or palettes")
    key = next(iter(template))
    rows = template[key]
    limit = MAX_ORDINARY_THREE_COLOR_SIZE if three_colors and key == "colors" else MAX_TEMPLATE_SIZE
    if not isinstance(rows, list) or not 2 <= len(rows) <= limit:
        raise ValueError(f"expected a {key} array of length 2 to {limit}")
    if key == "colors":
        if any(type(label) is not int or label < 0 for label in rows):
            raise ValueError("color labels must be nonnegative integers")
        return [frozenset((label,)) for label in rows], len(set(rows)), 1
    palettes = []
    universe = set()
    for row in rows:
        if not isinstance(row, list) or not row or any(type(t) is not int or t < 0 for t in row):
            raise ValueError("each palette must be a nonempty array of nonnegative integer labels")
        labels = frozenset(row)
        if len(labels) != len(row):
            raise ValueError("a palette cannot contain duplicate labels")
        palettes.append(labels)
        universe.update(labels)
    return palettes, len(universe), min(map(len, palettes))


def _minimum_cover_partition(rows):
    """Partition the four positions into as few common-label groups as possible."""
    a, b, c, d = rows
    ab, cd = a & b, c & d
    if ab and cd:
        if not ab.isdisjoint(cd):
            return ((0, 1, 2, 3),)
        return ((0, 1), (2, 3))
    # Every triple contains the first two positions or the last two positions.
    if not ab.isdisjoint(c):
        return ((0, 1, 2), (3,))
    if not ab.isdisjoint(d):
        return ((0, 1, 3), (2,))
    if not cd.isdisjoint(a):
        return ((0, 2, 3), (1,))
    if not cd.isdisjoint(b):
        return ((1, 2, 3), (0,))
    ac, bd = not a.isdisjoint(c), not b.isdisjoint(d)
    if ac and bd:
        return ((0, 2), (1, 3))
    ad, bc = not a.isdisjoint(d), not b.isdisjoint(c)
    if ad and bc:
        return ((0, 3), (1, 2))
    for shared, i, j, k, l in (
        (ab, 0, 1, 2, 3), (cd, 2, 3, 0, 1), (ac, 0, 2, 1, 3),
        (bd, 1, 3, 0, 2), (ad, 0, 3, 1, 2), (bc, 1, 2, 0, 3),
    ):
        if shared:
            return ((i, j), (k,), (l,))
    return ((0,), (1,), (2,), (3,))


def _ordinary_three_color_counts(colors: list[int]):
    m = len(colors)
    full = (1 << m) - 1
    indices = {label: i for i, label in enumerate(dict.fromkeys(colors))}
    codes = [indices[label] for label in colors]
    planes = []
    for bit in range((len(indices) - 1).bit_length()):
        plane = sum(1 << i for i, code in enumerate(codes) if (code >> bit) & 1)
        planes.append((plane, plane | (plane << m)))

    # equals[t] has bit x exactly when color[x] == color[x+t] modulo m.
    equals = []
    for offset in range(m):
        differences = 0
        for plane, doubled in planes:
            differences |= plane ^ (doubled >> offset)
        equals.append(full & ~differences)

    def shifted(bits: int, offset: int) -> int:
        return (bits >> offset) | ((bits << (m - offset)) & full)

    histogram = [0] * 5
    first = None
    for step in range(1, m):
        twice = (2 * step) % m
        # A position repeats if it matches any earlier position in this 4-AP.
        # With k repeats, the four positions use exactly 4-k distinct labels.
        repeat1 = equals[step]
        repeat2 = equals[twice] | shifted(equals[step], step)
        repeat3 = equals[(3 * step) % m] | shifted(equals[twice], step) | shifted(equals[step], twice)
        either = repeat1 | repeat2
        both = repeat1 & repeat2
        any_repeat = (either | repeat3).bit_count()
        violations = both | (either & repeat3)
        at_least_two = violations.bit_count()
        all_three = (both & repeat3).bit_count()
        histogram[1] += all_three
        histogram[2] += at_least_two - all_three
        histogram[3] += any_repeat - at_least_two
        histogram[4] += m - any_repeat
        if violations:
            start = (violations & -violations).bit_length() - 1
            if first is None or (start, step) < first:
                first = (start, step)

    witness = None
    if first is not None:
        start, step = first
        positions = [(start + j * step) % m for j in range(4)]
        labels = [colors[i] for i in positions]
        witness = {"start": start, "step": step, "positions": positions,
                   "chosen_labels": labels, "cover": sorted(set(labels))}
    return histogram, witness


def _fractional_three_color_counts(entries: list[frozenset[int]]):
    m = len(entries)
    histogram = [0] * 5
    first_witness = None
    for start in range(m):
        for step in range(1, m):
            positions = (start, (start + step) % m, (start + 2 * step) % m, (start + 3 * step) % m)
            rows = tuple(entries[i] for i in positions)
            partition = _minimum_cover_partition(rows)
            count = len(partition)
            histogram[count] += 1
            if count <= 2 and first_witness is None:
                cover = {min(frozenset.intersection(*(rows[i] for i in group))) for group in partition}
                # Repeated visits to the same residue receive the same label.
                labels = [min(row & cover) for row in rows]
                first_witness = {"start": start, "step": step, "positions": list(positions),
                                 "chosen_labels": labels, "cover": sorted(set(labels))}
    return histogram, first_witness


def _verify_three_colors(template: Any) -> dict[str, Any]:
    # The archive's modulus and origin identify the positions. Recompute every
    # certificate field, including palette cardinality and progression counts.
    if isinstance(template, dict) and "modulus" in template:
        payload = {key: template[key] for key in ("colors", "palettes") if key in template}
        entries, a, b = parse_template(payload, three_colors=True)
        if type(template["modulus"]) is not int or template["modulus"] != len(entries):
            raise ValueError("modulus must equal the number of template positions")
        origin = template.get("first_residue", 0)
        if type(origin) is not int or origin != 0:
            raise ValueError("the template must begin at residue zero")
        template = payload
    else:
        entries, a, b = parse_template(template, three_colors=True)

    m = len(entries)
    colors = template.get("colors")
    if colors is not None:
        histogram, first_witness = _ordinary_three_color_counts(colors)
    else:
        histogram, first_witness = _fractional_three_color_counts(entries)

    valid = histogram[1] + histogram[2] == 0
    lhs, rhs = m**5 * b**21, a**21
    # Smallest integer modulus m with m^5*b^21 > a^21, including equality.
    lo, hi = 0, 1 << ((rhs.bit_length() + 4) // 5)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if mid**5 * b**21 > rhs:
            hi = mid
        else:
            lo = mid
    return {
        "kind": "cyclic_three_colors" if colors is not None else "cyclic_fractional_three_colors",
        "m": m,
        **({"color_count": a} if colors is not None else {"palette_size": a, "min_labels_per_position": b}),
        "checked_progressions": m * (m - 1), "valid": valid,
        "minimum_cover_histogram": {str(i): histogram[i] for i in range(1, 5)},
        "violation_count": histogram[1] + histogram[2], "first_witness": first_witness,
        "five_over_twenty_one_threshold": {
            "m_to_5_times_b_to_21": lhs, "a_to_21": rhs,
            "least_modulus_for_palette": hi, "strict_inequality_holds": lhs > rhs,
        },
        "improves_quarter_via_lift": valid and m * b**4 > a**4,
        "improves_five_over_twenty_one_via_lift": valid and lhs > rhs,
    }


def verify_template(template: Any, *, three_colors: bool = False) -> dict[str, Any]:
    """Use every nonzero residue as a step, including non-generators."""
    if three_colors:
        return _verify_three_colors(template)
    entries, a, b = parse_template(template)
    m = len(entries)
    ordinary = "colors" in template
    violations = 0
    first_witness = None
    for start in range(m):
        for step in range(1, m):
            last = (start + 3 * step) % m
            if entries[start].isdisjoint(entries[last]):
                continue
            inner_left = (start + step) % m
            inner_right = (start + 2 * step) % m
            if not entries[inner_left].isdisjoint(entries[inner_right]):
                violations += 1
                if first_witness is None:
                    positions = [start, inner_left, inner_right, last]
                    first_witness = {"start": start, "step": step, "positions": positions}
                    if ordinary:
                        first_witness["colors"] = [template["colors"][i] for i in positions]
                    else:
                        first_witness["outer_common_label"] = min(entries[start] & entries[last])
                        first_witness["inner_common_label"] = min(entries[inner_left] & entries[inner_right])
    return {
        "kind": "cyclic_ABBA" if ordinary else "cyclic_fractional_ABBA", "m": m,
        **({"color_count": a} if ordinary else {"palette_size": a, "min_labels_per_position": b}),
        "checked_progressions": m * (m - 1), "valid": violations == 0,
        "violation_count": violations, "first_witness": first_witness,
        "improves_quarter_via_lift": violations == 0 and m * b ** 4 > a ** 4,
        "improves_five_over_twenty_one_via_lift": violations == 0 and m ** 5 * b ** 21 > a ** 21,
    }
