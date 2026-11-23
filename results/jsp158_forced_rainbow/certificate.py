"""Exact rainbow counts for four-term progressions in ordinary integer intervals."""

from collections import Counter


def prefix_counts(length, budget):
    """Count first-occurrence-normalized legal words with at most `budget` rainbows."""
    counts = [[0] * (budget + 1) for _ in range(length + 1)]
    ending = [
        [(i - 3 * d, i - 2 * d, i - d) for d in range(1, i // 3 + 1)]
        for i in range(length)
    ]
    word = [0] * length

    def extend(i, used, cost):
        counts[i][cost] += 1
        if i == length:
            return
        forbidden = 0
        distinct_triples = 0
        saved = [0] * (used + 1)
        for a, b, c in ending[i]:
            x, y, z = word[a], word[b], word[c]
            if x == y == z:
                return
            if x == y or y == z or z == x:
                forbidden |= (1 << x) | (1 << y) | (1 << z)
            else:
                distinct_triples += 1
                saved[x] += 1
                saved[y] += 1
                saved[z] += 1
        for color, credit in enumerate(saved):
            next_cost = cost + distinct_triples - credit
            if forbidden & (1 << color) or next_cost > budget:
                continue
            word[i] = color
            extend(i + 1, max(used, color + 1), next_cost)

    extend(0, 0, 0)
    return counts


def spectrum(word):
    return sorted(Counter(
        len({word[x + k * d] for k in range(4)})
        for d in range(1, (len(word) - 1) // 3 + 1)
        for x in range(len(word) - 3 * d)
    ).items())


if __name__ == "__main__":
    counts = prefix_counts(25, 6)
    print("length 0..19, no rainbow:", [row[0] for row in counts[:20]])
    print("normalized prefixes, at most 6 rainbows:", sum(map(sum, counts)))
    print("length 25, exactly 0..6 rainbows:", counts[25])
    print("minimum at lengths 19..24:", [next(j for j, n in enumerate(row) if n)
                                            for row in counts[19:25]])
    for witness in ("001213302331012204", "0012003432214431301300144"):
        print(witness, spectrum(witness))
