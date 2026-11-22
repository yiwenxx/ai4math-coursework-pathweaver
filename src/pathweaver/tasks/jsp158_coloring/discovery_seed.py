"""Handwritten standard-library seed; every accepted recoloring preserves validity."""
import random
import time


def _solution(instance, colors):
    # Relabel without altering equality patterns or the number of used colors.
    labels = {}
    canonical = [labels.setdefault(color, len(labels)) for color in colors]
    return {"schema_version": 1, "task_id": instance["task_id"],
            "instance_id": instance["instance_id"], "solution": {"colors": canonical}}


def _allows_recolor(colors, position, target, deadline):
    """Check all progressions containing position; None means no move was committed."""
    n = len(colors)
    checked = 0
    for role in range(4):
        max_step = n
        if role:
            max_step = min(max_step, position // role)
        if role < 3:
            max_step = min(max_step, (n - 1 - position) // (3 - role))
        for step in range(1, max_step + 1):
            if checked % 64 == 0 and time.monotonic() >= deadline:
                return None
            start = position - role * step
            labels = {target if offset == role else colors[start + offset * step]
                      for offset in range(4)}
            checked += 1
            if len(labels) < 3:
                return False
    return True


def solve(instance, budget):
    """Return a legal coloring, even when descent stops early at its local budget."""
    n = instance["data"]["n"]
    wall_seconds = budget["wall_seconds"]
    seed = budget["seed"]
    max_evaluations = budget.get("max_evaluations", 10000)

    deadline = time.monotonic() + 0.8 * wall_seconds
    rng = random.Random(seed)
    colors = list(range(n))  # All APs have four distinct colors initially.
    counts = dict.fromkeys(colors, 1)
    attempts = 0
    for _ in range(4):
        order = list(range(n))
        rng.shuffle(order)
        order.sort(key=lambda index: counts[colors[index]])
        changed = False
        for position in order:
            old = colors[position]
            targets = sorted((color for color in counts if color != old),
                             key=lambda color: (-counts[color], color))
            for target in targets:
                if attempts >= max_evaluations or time.monotonic() >= deadline:
                    return _solution(instance, colors)
                attempts += 1
                allowed = _allows_recolor(colors, position, target, deadline)
                if allowed is None:
                    return _solution(instance, colors)
                if allowed:
                    # Only APs containing position change, and all were checked.
                    colors[position] = target
                    counts[target] += 1
                    counts[old] -= 1
                    if not counts[old]:
                        del counts[old]
                    changed = True
                    break
        if not changed:
            break
    return _solution(instance, colors)
