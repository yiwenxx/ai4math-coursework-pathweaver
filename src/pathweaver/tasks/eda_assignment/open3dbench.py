"""Import a published Open3DBench two-die placement as a coupled TaskPack.

The deliberately narrow importer preserves the internal data graph using real
Liberty combinational arcs and explicit HBT_BOTIN/HBT_TOPIN components. Delays
are geometric proxies, with zero cell-arc delay, not characterized timing.
Exact rational LEF geometry is converted to integer coordinates without rounding.
The returned source records support a separate geometry audit without consulting
TaskPack edges or its evaluator. Importing never invokes a solver.
"""
from collections import defaultdict, deque
from fractions import Fraction
import heapq
import json
from math import lcm
from pathlib import Path
import re
from typing import Any, Sequence


SKIPPED_NETS = {
    "clk_i", "rst_n_i", "clk", "p_bsg_tag_clk_i", "p_clk_A_i", "p_clk_B_i",
    "p_clk_C_i", "p_ci_clk_i", "p_ci2_tkn_i", "p_co_clk_i", "p_co2_tkn_i",
}
HBT_MASTERS = {"HBT_BOTIN", "HBT_TOPIN"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return data.decode("utf-8"), {
        "name": path.name, "bytes": len(data),
    }


def exact(value):
    value = Fraction(value)
    return value.numerator if value.denominator == 1 else str(value)


def strip_comments(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def groups(text):
    """Return direct Liberty child groups, skipping each balanced child body."""
    pattern = re.compile(r"([A-Za-z_]\w*)\s*\(([^)]*)\)\s*\{")
    result, position = [], 0
    while match := pattern.search(text, position):
        depth, quote, escape = 1, False, False
        end = match.end()
        while end < len(text) and depth:
            char = text[end]
            if escape:
                escape = False
            elif quote and char == "\\":
                escape = True
            elif char == '"':
                quote = not quote
            elif not quote:
                depth += (char == "{") - (char == "}")
            end += 1
        require(depth == 0, f"unbalanced Liberty group {match[1]}")
        result.append((match[1], match[2].strip().strip('"'), text[match.end():end - 1], match.start(), end))
        position = end
    return result


def attributes(text, child_groups):
    pieces, previous = [], 0
    for _, _, _, start, end in child_groups:
        pieces.append(text[previous:start])
        previous = end
    pieces.append(text[previous:])
    result = {}
    for match in re.finditer(r'(\w+)\s*:\s*("(?:\\.|[^"\\])*"|[^;]+)\s*;', "".join(pieces)):
        result[match[1]] = match[2].strip().strip('"')
    return result


def identifiers(expression):
    return set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expression))


def parse_liberty(path):
    text, source = read(path)
    libraries = [g for g in groups(strip_comments(text)) if g[0] == "library"]
    require(len(libraries) == 1, "expected exactly one Liberty library")
    cells = {}
    for name, master, body, _, _ in groups(libraries[0][2]):
        if name != "cell":
            continue
        require(master not in cells, f"duplicate Liberty cell {master}")
        children = groups(body)
        cell_attributes = attributes(body, children)
        sequential = [g for g in children if g[0] in {"ff", "latch"}]
        is_gate = "clock_gating_integrated_cell" in cell_attributes
        controls, data = set(), set()
        for kind, _, state_body, _, _ in sequential:
            state_attrs = attributes(state_body, groups(state_body))
            data |= identifiers(state_attrs.get("next_state" if kind == "ff" else "data_in", ""))
            for key in ("clocked_on", "clocked_on_also", "enable", "clear", "preset"):
                controls |= identifiers(state_attrs.get(key, ""))
        pins, arcs, internal_nodes = {}, set(), []
        for kind, pin, pin_body, _, _ in children:
            if kind in {"bus", "bundle"}:
                raise ValueError(f"Liberty bus/bundle unsupported in master {master}")
            if kind != "pin":
                continue
            pin_groups = groups(pin_body)
            attrs = attributes(pin_body, pin_groups)
            direction = attrs.get("direction")
            if direction == "internal":
                require(attrs.get("internal_node") == pin, f"undocumented internal Liberty node {master}/{pin}")
                internal_nodes.append(pin)
                continue
            require(direction in {"input", "output", "inout"}, f"missing/unknown direction {master}/{pin}")
            require(pin not in pins, f"duplicate Liberty pin {master}/{pin}")
            if attrs.get("clock") == "true" or any(
                attrs.get(key) == "true" for key in (
                    "clock_gate_clock_pin", "clock_gate_enable_pin", "clock_gate_test_pin", "clock_gate_out_pin",
                )
            ):
                controls.add(pin)
            if attrs.get("signal_type") in {"test_scan_enable", "test_scan_clock", "test_scan_clock_a", "test_scan_clock_b"}:
                controls.add(pin)
            pins[pin] = {"direction": direction, "attributes": attrs}
            for group_kind, _, timing_body, _, _ in pin_groups:
                if group_kind != "timing" or direction != "output" or sequential or is_gate:
                    continue
                timing_attrs = attributes(timing_body, groups(timing_body))
                timing_type = timing_attrs.get("timing_type", "combinational")
                if timing_type not in {"combinational", "combinational_rise", "combinational_fall"}:
                    continue
                related = timing_attrs.get("related_pin", "").split()
                require(related, f"output timing group missing related_pin: {master}/{pin}")
                for related_pin in related:
                    arcs.add((related_pin, pin))
        for source_pin, output_pin in arcs:
            require(source_pin in pins and pins[source_pin]["direction"] == "input", f"unknown/non-input Liberty arc {master}/{source_pin}->{output_pin}")
        for pin, description in pins.items():
            if is_gate:
                role = "clock_control"
            elif sequential:
                role = "data" if description["direction"] == "output" or (pin in data and pin not in controls) else "clock_control"
            else:
                role = "clock_control" if pin in controls else "data"
            description["role"] = role
        cells[master] = {"pins": pins, "arcs": sorted(arcs), "sequential": bool(sequential), "clock_gate": is_gate, "internal_nodes": internal_nodes}
    require(cells, "no Liberty cells")
    return cells, source


def parse_lef(paths):
    if isinstance(paths, (str, Path)):
        paths = [paths]
    macros, sources = {}, []
    for path in paths:
        text, source = read(path)
        sources.append(source)
        text = re.sub(r"#[^\n]*", "", text)
        for match in re.finditer(r"(?ms)^\s*MACRO\s+(\S+)\s*\n(.*?)^\s*END\s+\1\s*$", text):
            name, body = match[1], match[2]
            require(name not in macros, f"duplicate LEF master {name}")
            size = re.search(r"\bSIZE\s+(\S+)\s+BY\s+(\S+)\s*;", body)
            origin = re.search(r"\bORIGIN\s+(\S+)\s+(\S+)\s*;", body)
            require(size is not None, f"LEF master without SIZE: {name}")
            require(origin is None or (Fraction(origin[1]), Fraction(origin[2])) == (0, 0), f"nonzero LEF ORIGIN unsupported: {name}")
            width, height = Fraction(size[1]), Fraction(size[2])
            pins = {}
            for pin_match in re.finditer(r"(?ms)^\s*PIN\s+(\S+)\s*\n(.*?)^\s*END\s+\1\s*$", body):
                pin, pin_body = pin_match[1], pin_match[2]
                direction = re.search(r"\bDIRECTION\s+(\S+)\s*;", pin_body)
                use = re.search(r"\bUSE\s+(\S+)\s*;", pin_body)
                rectangles = [tuple(Fraction(value) for value in rect) for rect in re.findall(r"\bRECT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s*;", pin_body)]
                require(pin not in pins, f"duplicate LEF pin {name}/{pin}")
                require(not re.search(r"\bPOLYGON\b", pin_body), f"polygon LEF pin unsupported: {name}/{pin}")
                require(rectangles and direction, f"missing LEF geometry/direction: {name}/{pin}")
                xs = [point for x1, _, x2, _ in rectangles for point in (x1, x2)]
                ys = [point for _, y1, _, y2 in rectangles for point in (y1, y2)]
                pins[pin] = {
                    "offset": ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2),
                    "direction": direction[1].lower(), "use": use[1] if use else "SIGNAL",
                }
            macros[name] = {"width": width, "height": height, "pins": pins}
    require(macros, "no LEF macros")
    return macros, sources


def parse_def(path):
    text, source = read(path)
    units = re.search(r"\bUNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;", text)
    die = re.search(r"\bDIEAREA\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s*;", text)
    require(units and die, "DEF requires units and rectangular DIEAREA")
    counts = {}
    def section(name):
        match = re.search(rf"\b{name}\s+(\d+)\s*;(.*?)\bEND\s+{name}\b", text, re.S)
        require(match is not None, f"DEF missing {name}")
        records = re.findall(r"(?ms)^\s*-\s+(.*?);", match[2])
        counts[name] = {"declared": int(match[1]), "actual": len(records)}
        return records
    components = {}
    for record in section("COMPONENTS"):
        header = record.split()
        require(len(header) >= 2, "invalid component record")
        identifier, master = header[:2]
        placement = re.search(r"\+\s*(PLACED|FIXED)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\S+)", record)
        require(identifier not in components and placement, f"duplicate/unplaced component {identifier}")
        components[identifier] = {"master": master, "x": int(placement[2]), "y": int(placement[3]), "orientation": placement[4]}
    nets = {}
    for record in section("NETS"):
        name = record.split()[0]
        require(name not in nets, f"duplicate DEF net {name}")
        pins = re.findall(r"\(\s*(\S+)\s+(\S+)\s*\)", record.split("+", 1)[0])
        require(len(pins) == len(set(pins)), f"duplicate DEF connection in {name}")
        nets[name] = pins
    return {"components": components, "nets": nets, "units": int(units[1]), "die": tuple(map(int, die.groups())), "counts": counts}, source


def transformed(x, y, width, height, orientation):
    # Placement is the lower-left of the oriented macro bounding rectangle.
    choices = {
        "N": (x, y), "S": (width - x, height - y),
        "FN": (width - x, y), "FS": (x, height - y),
        "E": (y, width - x), "W": (height - y, x),
        "FE": (y, x), "FW": (height - y, width - x),
    }
    require(orientation in choices, f"unsupported DEF orientation {orientation}")
    return choices[orientation]


def shortest_matching(domains):
    """Feasibility-only augmentations and a Hall-deficient alternating witness."""
    assignment, occupant = {}, {}
    for edge in sorted(domains, key=lambda name: (len(domains[name]), name)):
        queue, reached_edges, parent = deque([edge]), {edge}, {}
        free = None
        while queue and free is None:
            current = queue.popleft()
            for site in domains[current]:
                if site in parent:
                    continue
                parent[site] = current
                if site not in occupant:
                    free = site
                    break
                if occupant[site] not in reached_edges:
                    reached_edges.add(occupant[site])
                    queue.append(occupant[site])
        if free is None:
            return {"complete": False, "hall_edges": sorted(reached_edges), "hall_sites": sorted(parent), "deficiency": len(reached_edges) - len(parent)}
        while free is not None:
            current = parent[free]
            previous = assignment.get(current)
            assignment[current], occupant[free] = free, current
            free = previous
    return {"complete": True, "deficiency": 0}


def import_coupled_def(
    def_path: str | Path,
    lef_path: str | Path | Sequence[str | Path],
    lib_path: str | Path,
    *,
    instance_id: str,
) -> dict[str, Any]:
    """Return instance, published reference, provenance, admission and source graph.

    ``lef_path`` accepts both official bottom/upper LEFs. Invalid or unsupported
    source structures raise ``ValueError``. A structurally valid source can still
    fail the explicit coupling/competition/physical-geometry admission gate;
    callers must inspect ``admission.accepted`` before using it as a benchmark.
    All source-graph coordinates and dimensions use the manifest's exact integer
    scale relative to DEF database units.
    """
    require(isinstance(instance_id, str) and instance_id.strip(), "instance_id required")
    library, lib_source = parse_liberty(lib_path)
    macros, lef_sources = parse_lef(lef_path)
    design, def_source = parse_def(def_path)
    components, source_nets, units = design["components"], design["nets"], design["units"]
    pin_info, hbts, cell_models = {}, {}, {}
    for name, component in components.items():
        master, orientation = component["master"], component["orientation"]
        require(master in macros, f"unknown LEF master {master} on {name}")
        macro = macros[master]
        if master in HBT_MASTERS:
            require(orientation == "N", f"HBT orientation must be N: {name}")
            width, height = macro["width"] * units, macro["height"] * units
            center = (Fraction(component["x"]) + width / 2, Fraction(component["y"]) + height / 2)
            require(set(macro["pins"]) == {"TOP", "BOT"}, f"unsupported HBT pin set {master}")
            for pin, info in macro["pins"].items():
                require(info["offset"] == (macro["width"] / 2, macro["height"] / 2), f"HBT pins must be colocated at center: {master}/{pin}")
            hbts[name] = {"center": center, "width": width, "height": height, "master": master, "ports": {}}
            continue
        suffix = "_bottom" if master.endswith("_bottom") else "_upper" if master.endswith("_upper") else None
        require(suffix is not None, f"component without explicit source die suffix: {name} {master}")
        model_name = master[:-len(suffix)]
        require(model_name in library, f"unknown Liberty master {model_name} on {name}")
        cell = library[model_name]
        cell_models[name] = cell
        for pin, info in cell["pins"].items():
            require(pin in macro["pins"], f"Liberty pin missing from LEF: {master}/{pin}")
            geometry = macro["pins"][pin]
            require(geometry["direction"] == info["direction"], f"Liberty/LEF direction mismatch {master}/{pin}")
            x, y = transformed(*geometry["offset"], macro["width"], macro["height"], orientation)
            pin_info[(name, pin)] = {
                "x": Fraction(component["x"]) + x * units,
                "y": Fraction(component["y"]) + y * units,
                "tier": 0 if suffix == "_bottom" else 1,
                "direction": info["direction"], "role": info["role"],
                "master": model_name,
            }
    require(hbts, "reference contains no explicit HBTs")
    connected, pin_nets = set(), {}
    for name, pins in source_nets.items():
        for instance, pin in pins:
            if instance == "PIN":
                continue
            require(instance in components, f"net {name} references unknown instance {instance}")
            if instance in hbts:
                require(pin in {"TOP", "BOT"} and pin not in hbts[instance]["ports"], f"duplicate/unknown HBT port {instance}/{pin}")
                hbts[instance]["ports"][pin] = name
            else:
                require((instance, pin) in pin_info, f"unknown Liberty/LEF pin in net {name}: {instance}/{pin}")
                require((instance, pin) not in pin_nets, f"pin belongs to multiple nets: {instance}/{pin}")
                pin_nets[(instance, pin)] = name
                connected.add((instance, pin))
    reconstructed, consumed = {}, set()
    for hbt, info in hbts.items():
        require(set(info["ports"]) == {"BOT", "TOP"}, f"HBT must connect exactly two split nets: {hbt}")
        names = [info["ports"][port] for port in ("BOT", "TOP")]
        require(names[0].endswith("_BOT") and names[1] == names[0][:-4] + "_TOP", f"non-paired HBT split names {hbt}: {names}")
        base = names[0][:-4]
        require(base not in reconstructed, f"duplicate reconstructed net {base}")
        real_pins = []
        for port, name in zip(("BOT", "TOP"), names):
            require(name not in consumed, f"split net {name} joins multiple HBTs")
            consumed.add(name)
            for instance, pin in source_nets[name]:
                if instance == hbt:
                    continue
                require(instance not in hbts, f"split net {name} contains multiple HBTs")
                if instance != "PIN":
                    require(pin_info[(instance, pin)]["tier"] == (0 if port == "BOT" else 1), f"HBT split net/die mismatch {name}: {instance}/{pin}")
                real_pins.append((instance, pin))
        reconstructed[base] = {"pins": real_pins, "hbt": hbt, "source_nets": names}
    for name, pins in source_nets.items():
        if name not in consumed:
            require(name not in reconstructed, f"duplicate reconstructed net name {name}")
            reconstructed[name] = {"pins": pins, "hbt": None, "source_nets": [name]}

    nodes, edges, selected, assignments = {}, [], {}, {}
    source_arcs, retained_net_records = [], {}
    excluded_nets, excluded_pins, fixed_without_path = [], [], []
    def node_id(pin):
        return json.dumps(pin, separators=(",", ":"))
    for pin in sorted(connected):
        info = pin_info[pin]
        if info["role"] == "data":
            identifier = node_id(pin)
            nodes[identifier] = {"id": identifier, "x": info["x"], "y": info["y"], "tier": info["tier"]}
        else:
            excluded_pins.append({"instance": pin[0], "pin": pin[1], "master": info["master"], "reason": "Liberty sequential/clock-control boundary"})
    arc_count = 0
    def fixed(source, target, delay, kind, provenance):
        edges.append({"id": f"e{len(edges)}", "source": source, "target": target, "delay": delay, "kind": kind, "provenance": provenance})
    def distance(left, right):
        return abs(left[0] - right[0]) + abs(left[1] - right[1])
    def xy(pin):
        return pin_info[pin]["x"], pin_info[pin]["y"]
    for name, cell in cell_models.items():
        for input_pin, output_pin in cell["arcs"]:
            left, right = node_id((name, input_pin)), node_id((name, output_pin))
            if left in nodes and right in nodes:
                fixed(left, right, Fraction(0), "liberty_combinational_arc", {"instance": name, "related_pin": input_pin, "output_pin": output_pin})
                source_arcs.append({"source": left, "target": right})
                arc_count += 1
    for name, net in reconstructed.items():
        all_pins, hbt = net["pins"], net["hbt"]
        reason = "upstream_clock_reset_exclusion" if name in SKIPPED_NETS else "top_level_io_boundary" if any(pin[0] == "PIN" for pin in all_pins) else None
        if reason:
            excluded_nets.append({"net": name, "reason": reason, "hbt": hbt, "source_nets": net["source_nets"]})
            continue
        require(all(pin_info[pin]["direction"] in {"input", "output"} for pin in all_pins), f"bidirectional/unsupported signal direction on {name}")
        drivers = [pin for pin in all_pins if pin_info[pin]["direction"] == "output"]
        require(len(drivers) == 1, f"net {name} requires exactly one real driver, found {len(drivers)}")
        driver = drivers[0]
        if pin_info[driver]["role"] != "data":
            excluded_nets.append({"net": name, "reason": "Liberty_clock_control_driver", "hbt": hbt, "source_nets": net["source_nets"]})
            continue
        sinks = [pin for pin in all_pins if pin != driver and pin_info[pin]["role"] == "data"]
        if not sinks:
            excluded_nets.append({"net": name, "reason": "no_internal_data_sink", "hbt": hbt, "source_nets": net["source_nets"]})
            continue
        driver_tier = pin_info[driver]["tier"]
        local = [pin for pin in sinks if pin_info[pin]["tier"] == driver_tier]
        remote = [pin for pin in sinks if pin_info[pin]["tier"] != driver_tier]
        retained_net_records[name] = {
            "driver": node_id(driver),
            "local_sinks": [node_id(pin) for pin in local],
            "remote_sinks": [node_id(pin) for pin in remote],
            "hbt": f"site:{hbt}" if hbt else None,
            "selected": len(all_pins) == 2 and len(remote) == 1,
            "source_nets": net["source_nets"],
        }
        for sink in local:
            fixed(node_id(driver), node_id(sink), distance(xy(driver), xy(sink)), "fixed_same_tier_net", {"net": name})
        if not remote:
            if hbt:
                fixed_without_path.append({"net": name, "hbt": hbt, "reason": "all_remote_sinks_are_control_boundaries"})
            continue
        require(hbt is not None, f"data net {name} crosses dies without a reference HBT")
        expected_master = "HBT_BOTIN" if driver_tier == 0 else "HBT_TOPIN"
        require(hbts[hbt]["master"] == expected_master, f"HBT direction disagrees with real driver of {name}")
        edge_id = f"cross:{name}"
        if len(all_pins) == 2 and len(remote) == 1:
            target = node_id(remote[0])
            selected[edge_id] = {"net": name, "driver": driver, "sink": remote[0], "hbt": hbt, "source_nets": net["source_nets"]}
        else:
            target = f"hbt_remote:{hbt}"
            hx, hy = hbts[hbt]["center"]
            nodes[target] = {"id": target, "x": hx, "y": hy, "tier": 1 - driver_tier}
            for sink in remote:
                fixed(target, node_id(sink), distance((hx, hy), xy(sink)), "fixed_remote_hbt_branch", {"net": name, "hbt": hbt})
        edges.append({"id": edge_id, "source": node_id(driver), "target": target, "base_delay": 0, "alpha": 1, "eligible_sites": [f"site:{hbt}"], "kind": "selected_two_pin_cross_net" if edge_id in selected else "fixed_cross_net", "provenance": {"net": name, "hbt": hbt}})
        assignments[edge_id] = f"site:{hbt}"
    require(selected, "no adjustable two-pin internal data cross-net")
    candidate_sites = sorted(f"site:{record['hbt']}" for record in selected.values())
    for edge in edges:
        if edge["id"] in selected:
            edge["eligible_sites"] = list(candidate_sites)

    scale = 1
    # Include control-boundary pins and footprint dimensions needed by the
    # independent source audit, not just vertices retained in the TaskPack.
    for pin in connected:
        info = pin_info[pin]
        scale = lcm(scale, info["x"].denominator, info["y"].denominator)
    for hbt in hbts.values():
        scale = lcm(scale, *(value.denominator for value in hbt["center"]))
        scale = lcm(scale, hbt["width"].denominator, hbt["height"].denominator)
    def integer(value):
        value = Fraction(value) * scale
        require(value.denominator == 1, "nonintegral scaled geometry")
        return value.numerator
    for node in nodes.values():
        node["x"], node["y"] = integer(node["x"]), integer(node["y"])
    sites = [{"id": f"site:{name}", "x": integer(info["center"][0]), "y": integer(info["center"][1])} for name, info in sorted(hbts.items())]
    for edge in edges:
        if "delay" in edge:
            edge["delay"] = integer(edge["delay"])
    # A topology-only dynamic program; no objective or baseline evaluation.
    outgoing, indegree = defaultdict(list), dict.fromkeys(nodes, 0)
    for edge in edges:
        outgoing[edge["source"]].append(edge)
        indegree[edge["target"]] += 1
    ready = [name for name, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order, depth, predecessor = [], dict.fromkeys(nodes, 0), {}
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for edge in outgoing[node]:
            target = edge["target"]
            candidate = depth[node] + (edge["id"] in selected)
            if candidate > depth[target]:
                depth[target], predecessor[target] = candidate, edge
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    require(len(order) == len(nodes), f"retained real data graph is cyclic; unresolved pins: {sorted(node for node, degree in indegree.items() if degree)[:30]}")
    end = max(sorted(nodes), key=lambda node: depth[node])
    max_selected = depth[end]
    path = []
    while end in predecessor:
        edge = predecessor[end]
        path.append({key: edge[key] for key in ("id", "source", "target", "kind", "provenance")})
        end = edge["source"]
    path.reverse()
    site_by_id = {site["id"]: site for site in sites}
    domains = {}
    for edge in edges:
        if edge["id"] not in selected:
            continue
        left, right = nodes[edge["source"]], nodes[edge["target"]]
        lengths = {site_id: abs(left["x"] - site_by_id[site_id]["x"]) + abs(left["y"] - site_by_id[site_id]["y"]) + abs(right["x"] - site_by_id[site_id]["x"]) + abs(right["y"] - site_by_id[site_id]["y"]) for site_id in candidate_sites}
        minimum = min(lengths.values())
        domains[edge["id"]] = sorted(site_id for site_id, length in lengths.items() if length == minimum)
    competition = shortest_matching(domains)
    if not competition["complete"]:
        competition["argmin_domains"] = {edge: domains[edge] for edge in competition["hall_edges"]}

    footprints = {(info["width"], info["height"]) for info in hbts.values()}
    centers = [info["center"] for info in hbts.values()]
    rectangles = []
    xl, yl, xh, yh = design["die"]
    for name, info in hbts.items():
        x, y = info["center"]
        box = (x - info["width"] / 2, y - info["height"] / 2, x + info["width"] / 2, y + info["height"] / 2)
        require(box[0] >= xl and box[1] >= yl and box[2] <= xh and box[3] <= yh, f"HBT footprint outside DEF die: {name}")
        rectangles.append((box, name))
    active, overlaps = [], []
    for box, name in sorted(rectangles):
        active = [(other, other_name) for other, other_name in active if other[2] > box[0]]
        for other, other_name in active:
            if min(other[3], box[3]) > max(other[1], box[1]):
                overlaps.append([other_name, name])
        active.append((box, name))
    capacity = len(assignments.values()) == len(set(assignments.values()))
    admission = {
        "dag": True, "selected_cross_edges_on_witness_path": max_selected,
        "path_witness": path, "shortest_site_matching": competition,
        "reference_assignment_capacity_one": capacity,
        "reference_hbt_centers_distinct": len(centers) == len(set(centers)),
        "all_hbt_footprints_equal": len(footprints) == 1,
        "all_hbt_footprints_inside_die": True,
        "reference_hbt_overlap_pairs": overlaps,
    }
    admission["accepted"] = max_selected >= 2 and not competition["complete"] and capacity and len(set(centers)) == len(centers) and len(footprints) == 1 and not overlaps
    clean_edges = [{key: value for key, value in edge.items() if key not in {"kind", "provenance"}} for edge in edges]
    instance = {"schema_version": 1, "task_id": "eda_assignment", "instance_id": instance_id, "data": {"nodes": list(nodes.values()), "sites": sites, "edges": clean_edges}}
    reference = {"schema_version": 1, "task_id": "eda_assignment", "instance_id": instance_id, "solution": {"assignment": assignments}, "provenance": "author-published converted DEF HBT assignments, not solver output"}
    manifest = {
        "sources": [def_source, *lef_sources, lib_source],
        "source_def_record_counts": design["counts"],
        "source_def_count_discrepancy": {name: counts for name, counts in design["counts"].items() if counts["declared"] != counts["actual"]},
        "source_def_count_discrepancy_note": "Upstream conversion retains old declared counts while inserting HBTs and split nets/removing TAPCELLs; complete semicolon records and all references were checked, source unmodified.",
        "def_units_per_micron": units, "coordinate_scale": scale,
        "selected_net_ids": [record["net"] for _, record in sorted(selected.items())],
        "selected_edges": {edge: {**record, "driver": list(record["driver"]), "sink": list(record["sink"])} for edge, record in selected.items()},
        "selected_net_count": len(selected), "total_hbt_count": len(hbts),
        "fixed_hbt_count": len(hbts) - len(selected),
        "all_hbt_sites": {name: {"center_dbu": [exact(value) for value in info["center"]], "width_dbu": exact(info["width"]), "height_dbu": exact(info["height"]), "master": info["master"], "split_nets": info["ports"]} for name, info in hbts.items()},
        "liberty_combinational_arcs": arc_count,
        "sequential_cell_count": sum(model["sequential"] for model in cell_models.values()),
        "clock_gate_cell_count": sum(model["clock_gate"] for model in cell_models.values()),
        "liberty_internal_state_nodes": {name: cell["internal_nodes"] for name, cell in library.items() if cell["internal_nodes"]},
        "node_count": len(nodes), "edge_count": len(edges),
        "reconstructed_net_count": len(reconstructed),
        "excluded_nets": excluded_nets, "excluded_control_pins": excluded_pins,
        "fixed_hbts_without_data_path": fixed_without_path,
        "scope": "Complete internal data graph of this published two-die placement, with explicit IO/clock/reset/control boundaries and sequential cell internal arcs removed.",
        "selection": "All and only two-pin cross-die internal data nets; no score-based selection.",
        "pin_geometry": "Exact Fraction center of the LEF pin rectangle union bounding box, transformed by DEF orientation and placed position.",
        "cell_arc_delay": 0,
        "fixed_cross_net_model": "One singleton-site crossing from real driver to remote virtual HBT center, then fixed same-tier Manhattan branches; one site per physical HBT regardless of fanout.",
        "objectives": "(T,L) lexicographic. T is full retained DAG geometric proxy path length, not timing. L sums TaskPack cross-edge geometry; omitted fixed remote branch lengths are constants, not claimed total HPWL.",
        "edge_provenance": {edge["id"]: {"kind": edge["kind"], **edge["provenance"]} for edge in edges},
    }
    split_net_records = {}
    for hbt, info in hbts.items():
        for name in info["ports"].values():
            real_pins = [pin for pin in source_nets[name] if pin[0] != hbt]
            require(all(pin[0] != "PIN" for pin in real_pins), f"top-level IO pin on HBT split net unsupported for source audit: {name}")
            split_net_records[name] = {
                "pins": [node_id(pin) for pin in real_pins], "hbt": f"site:{hbt}",
            }
    source_graph = {
        "coordinate_scale": scale, "def_units_per_micron": units,
        "pins": {
            node_id(pin): {
                "x": integer(pin_info[pin]["x"]),
                "y": integer(pin_info[pin]["y"]),
                **{key: pin_info[pin][key] for key in ("tier", "direction", "role", "master")},
            }
            for pin in sorted(connected)
        },
        "cell_arcs": source_arcs,
        "retained_nets": retained_net_records,
        "sites": {
            f"site:{name}": {
                "x": integer(info["center"][0]), "y": integer(info["center"][1]),
                "width": integer(info["width"]), "height": integer(info["height"]),
                "master": info["master"],
            }
            for name, info in sorted(hbts.items())
        },
        "split_nets": split_net_records,
    }
    return {
        "instance": instance, "reference_solution": reference, "manifest": manifest,
        "admission": admission, "source_graph": source_graph,
    }
