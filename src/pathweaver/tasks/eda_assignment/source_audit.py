"""Independent geometric-star audit using trusted physical source records.

Unlike the TaskPack evaluator, this reconstructs direct driver-to-sink arcs from
source nets. It does not use the projected TaskPack edges, its scoring routines,
or candidate-reported metrics. Source records come from the admitted importer.
"""
from collections import Counter, defaultdict, deque
from collections.abc import Mapping


def audit_coupled_assignment(bundle: Mapping, solution: Mapping) -> dict:
    source = bundle["source_graph"]
    reference = bundle["reference_solution"]
    if not isinstance(solution, Mapping):
        raise ValueError("solution must be a mapping")
    for key in ("schema_version", "task_id", "instance_id"):
        if solution.get(key) != reference[key] or (
            key == "schema_version" and type(solution.get(key)) is not int
        ):
            raise ValueError(f"source audit: mismatched {key}")
    payload = solution.get("solution")
    assignment = payload.get("assignment") if isinstance(payload, Mapping) else None
    original = reference["solution"]["assignment"]
    if not isinstance(assignment, Mapping) or assignment.keys() != original.keys():
        raise ValueError("source audit: incomplete or extra assignment keys")
    selected = set(bundle["manifest"]["selected_edges"])
    candidates = {original[edge] for edge in selected}
    occupied = set()
    for edge, site in assignment.items():
        if not isinstance(site, str) or site in occupied:
            raise ValueError("source audit: invalid site or capacity violation")
        if (edge in selected and site not in candidates) or (
            edge not in selected and site != original[edge]
        ):
            raise ValueError("source audit: eligibility or fixed HBT violation")
        occupied.add(site)

    pins, sites = source["pins"], source["sites"]
    positions = {name: (site["x"], site["y"]) for name, site in sites.items()}
    before = Counter(positions.values())
    for edge in selected:
        destination = sites[assignment[edge]]
        positions[original[edge]] = (destination["x"], destination["y"])
    preserved = before == Counter(positions.values())
    if not preserved:
        raise ValueError("source audit: complete HBT position multiset changed")
    footprints = {(site["width"], site["height"]) for site in sites.values()}
    if len(footprints) != 1:
        raise ValueError("source audit requires equal HBT footprints")

    def xy(pin):
        return pins[pin]["x"], pins[pin]["y"]

    def distance(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    outgoing = defaultdict(list)
    indegree = {pin: 0 for pin, info in pins.items() if info["role"] == "data"}

    def arc(left, right, length):
        if left not in indegree or right not in indegree:
            raise ValueError("source audit: arc crosses an excluded pin boundary")
        outgoing[left].append((right, length))
        indegree[right] += 1

    for item in source["cell_arcs"]:
        arc(item["source"], item["target"], 0)
    total_length = 0
    for net in source["retained_nets"].values():
        driver = net["driver"]
        for sink in net["local_sinks"]:
            arc(driver, sink, distance(xy(driver), xy(sink)))
        remote = net["remote_sinks"]
        if remote:
            hbt = positions[net["hbt"]]
            first_leg = distance(xy(driver), hbt)
            for sink in remote:
                arc(driver, sink, first_leg + distance(hbt, xy(sink)))
            total_length += first_leg
            if net["selected"]:
                if len(remote) != 1 or net["local_sinks"]:
                    raise ValueError("source audit: selected net is not two-pin")
                total_length += distance(hbt, xy(remote[0]))
    queue = deque(pin for pin, count in indegree.items() if count == 0)
    arrival = dict.fromkeys(indegree, 0)
    visited = 0
    while queue:
        pin = queue.popleft()
        visited += 1
        for target, weight in outgoing[pin]:
            arrival[target] = max(arrival[target], arrival[pin] + weight)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if visited != len(indegree):
        raise ValueError("source audit: reconstructed source data graph is cyclic")

    hpwl = 0
    for net in source["split_nets"].values():
        points = [xy(pin) for pin in net["pins"]] + [positions[net["hbt"]]]
        xs, ys = zip(*points)
        hpwl += max(xs) - min(xs) + max(ys) - min(ys)

    # Doubled coordinates avoid rounding when a rectangle has odd dimensions.
    rectangles = []
    for name, (x, y) in positions.items():
        width, height = sites[name]["width"], sites[name]["height"]
        rectangles.append((2 * x - width, 2 * y - height,
                           2 * x + width, 2 * y + height))
    active, overlaps = [], 0
    for box in sorted(rectangles):
        active = [other for other in active if other[2] > box[0]]
        overlaps += sum(min(other[3], box[3]) > max(other[1], box[1]) for other in active)
        active.append(box)
    return {
        "objectives": [max(arrival.values(), default=0), total_length],
        "total_split_hpwl": hpwl,
        "split_net_count": len(source["split_nets"]),
        "hbt_positions_preserved": preserved,
        "hbt_overlap_pairs": overlaps,
        "capacity_one": True,
        "method": "source driver-to-sink star graph; zero cell arcs; independent Kahn longest paths",
    }
