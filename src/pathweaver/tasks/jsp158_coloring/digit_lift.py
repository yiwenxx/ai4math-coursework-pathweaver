"""Check separation on every finite interval digit power, with exact integer carries."""
from collections import deque

from .cyclic import parse_template


def verify_digit_lift(template):
    labels, a, b = parse_template(template)
    m = len(labels)
    origin = (0, 0, 0, False)
    target = (0, 0, 0, True)
    parents = {origin: None}
    queue = deque([origin])
    while queue and target not in parents:
        state = queue.popleft()
        c1, c2, c3, positive = state
        for x in range(m):
            for t in range(m):
                q3, outer = divmod(x + 3 * t + c3, m)
                if labels[x].isdisjoint(labels[outer]):
                    continue
                q1, left = divmod(x + t + c1, m)
                q2, right = divmod(x + 2 * t + c2, m)
                if labels[left].isdisjoint(labels[right]):
                    continue
                successor = (q1, q2, q3, positive or t != 0)
                if successor not in parents:
                    parents[successor] = (state, x, t)
                    queue.append(successor)
                if successor == target:
                    break
            if target in parents:
                break

    witness = None
    if target in parents:
        # Backtracking visits the most significant digit first.
        state = target
        start = step = digits = 0
        while state != origin:
            state, x, t = parents[state]
            start, step = m * start + x, m * step + t
            digits += 1
        witness = {"digits": digits, "start": start, "step": step,
                   "positions": [start + i * step for i in range(4)]}
    return {
        "kind": "integer_digit_product_separation", "m": m,
        "palette_size": a, "min_labels_per_position": b,
        "valid": witness is None, "first_witness": witness,
        "discovered_states": len(parents),
        "positive_carries": sorted([c1, c2, c3] for c1, c2, c3, positive in parents if positive),
        "improves_quarter_via_lift": witness is None and m * b ** 4 > a ** 4,
        "improves_five_over_twenty_one_via_lift": witness is None and m ** 5 * b ** 21 > a ** 21,
    }
