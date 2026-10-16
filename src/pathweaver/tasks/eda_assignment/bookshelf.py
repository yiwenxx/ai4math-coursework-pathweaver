"""Exact geometry projection of one D2D terminal Bookshelf snapshot.

This narrow adapter accepts UCLA nodes/nets/pl 1.0 with north-oriented fixed
cells and uniformly sized movable HBTs. It projects all cross-die nets having
one cell pin on each die. It neither infers circuit timing nor changes the
partition, cell locations, excluded HBTs, or the occupied HBT position multiset.
"""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import lcm
from pathlib import Path
import re
from typing import Any


_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_ADAPTER = "d2d_terminal_bookshelf_two_pin_projection_v1"


@dataclass(frozen=True)
class _Node:
    width: Fraction
    height: Fraction
    terminal: bool


@dataclass(frozen=True)
class _Placement:
    x: Fraction
    y: Fraction
    fixed: bool


@dataclass(frozen=True)
class _Pin:
    node: str
    direction: str
    dx: Fraction
    dy: Fraction


@dataclass(frozen=True)
class _Snapshot:
    nodes: dict[str, _Node]
    placements: dict[str, _Placement]
    nets: dict[str, tuple[_Pin, ...]]
    pairs: dict[str, tuple[str, str]]
    selected: tuple[str, ...]
    scale: int
    files: dict[str, dict[str, Any]]


def _number(token: str, location: str) -> Fraction:
    if not _NUMBER.fullmatch(token):
        raise ValueError(f"{location}: expected a finite decimal coordinate, got {token!r}")
    return Fraction(token)


def _records(path: Path, kind: str) -> tuple[list[tuple[int, str]], dict[str, Any]]:
    content = path.read_bytes()
    records = [
        (number, line.split("#", 1)[0].strip())
        for number, line in enumerate(content.decode("utf-8-sig").splitlines(), 1)
        if line.split("#", 1)[0].strip()
    ]
    if not records or records[0][1].split() != ["UCLA", kind, "1.0"]:
        raise ValueError(f"{path.name}: expected UCLA {kind} 1.0 header")
    return records[1:], {"bytes": len(content)}


def _count(record: tuple[int, str], name: str, filename: str) -> int:
    match = re.fullmatch(rf"{name}\s*:\s*(\d+)", record[1])
    if match is None:
        raise ValueError(f"{filename}:{record[0]}: expected {name} count")
    return int(match[1])


def _parse_nodes(records: list[tuple[int, str]]) -> dict[str, _Node]:
    if len(records) < 2:
        raise ValueError("terminal.nodes: missing NumNodes or NumTerminals")
    expected_nodes = _count(records[0], "NumNodes", "terminal.nodes")
    expected_terminals = _count(records[1], "NumTerminals", "terminal.nodes")
    nodes: dict[str, _Node] = {}
    for number, line in records[2:]:
        tokens = line.split()
        where = f"terminal.nodes:{number}"
        if len(tokens) not in (3, 4) or (len(tokens) == 4 and tokens[3] != "terminal"):
            raise ValueError(f"{where}: expected node width height [terminal]")
        identifier = tokens[0]
        if identifier in nodes:
            raise ValueError(f"{where}: duplicate node ID {identifier!r}")
        width, height = _number(tokens[1], where), _number(tokens[2], where)
        if width < 0 or height < 0:
            raise ValueError(f"{where}: node dimensions must be nonnegative")
        nodes[identifier] = _Node(width, height, len(tokens) == 4)
    if len(nodes) != expected_nodes or sum(node.terminal for node in nodes.values()) != expected_terminals:
        raise ValueError("terminal.nodes: declared node/terminal counts do not match records")
    return nodes


def _parse_placements(records: list[tuple[int, str]], nodes: Mapping[str, _Node]) -> dict[str, _Placement]:
    placements: dict[str, _Placement] = {}
    for number, line in records:
        tokens = line.split()
        where = f"terminal.pl:{number}"
        if len(tokens) not in (5, 6) or tokens[3:5] != [":", "N"]:
            raise ValueError(f"{where}: expected node x y : N [/FIXED]; only orientation N is supported")
        if len(tokens) == 6 and tokens[5] != "/FIXED":
            raise ValueError(f"{where}: unsupported placement flag {tokens[5]!r}")
        identifier = tokens[0]
        if identifier not in nodes or identifier in placements:
            raise ValueError(f"{where}: unknown or duplicate node ID {identifier!r}")
        placement = _Placement(_number(tokens[1], where), _number(tokens[2], where), len(tokens) == 6)
        if placement.fixed != nodes[identifier].terminal:
            raise ValueError(f"{where}: terminal cells must be fixed and HBTs must be movable")
        placements[identifier] = placement
    if placements.keys() != nodes.keys():
        raise ValueError("terminal.pl: placements must cover every node exactly once")
    return placements


def _parse_nets(records: list[tuple[int, str]], nodes: Mapping[str, _Node]) -> dict[str, tuple[_Pin, ...]]:
    if len(records) < 2:
        raise ValueError("terminal.nets: missing NumNets or NumPins")
    expected_nets = _count(records[0], "NumNets", "terminal.nets")
    expected_pins = _count(records[1], "NumPins", "terminal.nets")
    nets: dict[str, tuple[_Pin, ...]] = {}
    index, pin_count = 2, 0
    while index < len(records):
        number, line = records[index]
        match = re.fullmatch(r"NetDegree\s*:\s*(\d+)\s+(\S+)", line)
        if match is None:
            raise ValueError(f"terminal.nets:{number}: expected NetDegree : count name")
        degree, identifier = int(match[1]), match[2]
        if identifier in nets:
            raise ValueError(f"terminal.nets:{number}: duplicate net ID {identifier!r}")
        if degree < 1 or index + degree >= len(records):
            raise ValueError(f"terminal.nets:{number}: invalid or truncated net degree")
        pins: list[_Pin] = []
        for pin_number, pin_line in records[index + 1:index + degree + 1]:
            tokens = pin_line.split()
            where = f"terminal.nets:{pin_number}"
            if len(tokens) != 5 or tokens[1] not in {"I", "O", "B"} or tokens[2] != ":":
                raise ValueError(f"{where}: expected node I/O/B : x_offset y_offset")
            if tokens[0] not in nodes:
                raise ValueError(f"{where}: unknown pin node {tokens[0]!r}")
            pins.append(_Pin(tokens[0], tokens[1], _number(tokens[3], where), _number(tokens[4], where)))
        nets[identifier] = tuple(pins)
        pin_count += degree
        index += degree + 1
    if len(nets) != expected_nets or pin_count != expected_pins:
        raise ValueError("terminal.nets: declared net/pin counts do not match records")
    return nets


def _center(nodes: Mapping[str, _Node], placements: Mapping[str, _Placement], node_id: str) -> tuple[Fraction, Fraction]:
    node, placement = nodes[node_id], placements[node_id]
    return placement.x + node.width / 2, placement.y + node.height / 2


def _point(snapshot: _Snapshot, pin: _Pin, centers: Mapping[str, tuple[Fraction, Fraction]] | None = None) -> tuple[Fraction, Fraction]:
    if centers is not None and pin.node in centers:
        x, y = centers[pin.node]
    else:
        x, y = _center(snapshot.nodes, snapshot.placements, pin.node)
    return x + pin.dx, y + pin.dy


def _load(directory: Path) -> _Snapshot:
    node_records, node_file = _records(directory / "terminal.nodes", "nodes")
    net_records, net_file = _records(directory / "terminal.nets", "nets")
    pl_records, pl_file = _records(directory / "terminal.pl", "pl")
    nodes = _parse_nodes(node_records)
    placements = _parse_placements(pl_records, nodes)
    nets = _parse_nets(net_records, nodes)
    split: dict[str, dict[int, str]] = {}
    cell_tiers: dict[str, int] = {}
    for name, pins in nets.items():
        match = re.fullmatch(r"(.+)_([01])", name)
        if match is None:
            raise ValueError(f"net {name!r}: only paired _0/_1 split nets are supported")
        base, tier = match[1], int(match[2])
        if base not in nodes or nodes[base].terminal:
            raise ValueError(f"net {name!r}: missing same-name movable HBT {base!r}")
        hbt_pins = [pin for pin in pins if not nodes[pin.node].terminal]
        if len(hbt_pins) != 1 or hbt_pins[0].node != base or hbt_pins[0].dx or hbt_pins[0].dy:
            raise ValueError(f"net {name!r}: requires exactly one same-name HBT with zero pin offset")
        if len(pins) < 2:
            raise ValueError(f"net {name!r}: requires at least one fixed cell pin")
        for pin in pins:
            if nodes[pin.node].terminal:
                if pin.node in cell_tiers and cell_tiers[pin.node] != tier:
                    raise ValueError(f"cell {pin.node!r}: inconsistent die partition across split nets")
                cell_tiers[pin.node] = tier
        split.setdefault(base, {})[tier] = name
    if any(sides.keys() != {0, 1} for sides in split.values()):
        raise ValueError("every cross-die net must have both _0 and _1 split sides")
    hbt_ids = {name for name, node in nodes.items() if not node.terminal}
    if hbt_ids != split.keys():
        raise ValueError("movable nodes must be exactly the paired split-net HBTs")
    dimensions = {(nodes[name].width, nodes[name].height) for name in hbt_ids}
    if len(dimensions) != 1 or any(width <= 0 or height <= 0 for width, height in dimensions):
        raise ValueError("all HBTs must have the same positive dimensions to preserve occupied footprints")
    centers = [_center(nodes, placements, name) for name in hbt_ids]
    if len(set(centers)) != len(centers):
        raise ValueError("distinct HBTs must have distinct physical center positions")
    pairs = {base: (sides[0], sides[1]) for base, sides in sorted(split.items())}
    selected = tuple(base for base, sides in pairs.items() if all(len(nets[name]) == 2 for name in sides))
    if not selected:
        raise ValueError("snapshot has no cross-die nets with exactly one cell pin on each side")
    scale = 1
    for pins in nets.values():
        for pin in pins:
            x, y = _center(nodes, placements, pin.node)
            scale = lcm(scale, (x + pin.dx).denominator, (y + pin.dy).denominator)
    files = {"terminal.nodes": node_file, "terminal.nets": net_file, "terminal.pl": pl_file}
    return _Snapshot(nodes, placements, nets, pairs, selected, scale, files)


def _scaled(value: Fraction, scale: int) -> int:
    result = value * scale
    if result.denominator != 1:
        raise ValueError("coordinate scale does not represent the exact source geometry")
    return result.numerator


def _exact(value: Fraction) -> int | str:
    return value.numerator if value.denominator == 1 else str(value)


def import_bookshelf(
    directory: Path, *, instance_id: str, source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Import every structurally eligible two-pin net, without score selection.

    The returned reference solution keeps each net's original HBT. The projected
    DAG has separate tier-0/tier-1 endpoint vertices for each selected net; its T
    is maximum selected interconnect length, not circuit delay or timing slack.
    All quantities are exact, with the minimal integer pin-coordinate scale.
    """
    if not isinstance(instance_id, str) or not instance_id.strip():
        raise ValueError("instance_id must be a nonempty string")
    if source is not None and not isinstance(source, Mapping):
        raise ValueError("source must be a metadata mapping")
    snapshot = _load(Path(directory))
    nodes, sites, edges, endpoints = [], [], [], {}
    site_ids = [f"site:{base}" for base in snapshot.selected]
    for base in snapshot.selected:
        endpoint_records = []
        for tier, name in enumerate(snapshot.pairs[base]):
            pin = next(pin for pin in snapshot.nets[name] if snapshot.nodes[pin.node].terminal)
            x, y = _point(snapshot, pin)
            nodes.append({"id": f"pin:{base}:{tier}", "x": _scaled(x, snapshot.scale), "y": _scaled(y, snapshot.scale), "tier": tier})
            endpoint_records.append({
                "split_net": name, "cell": pin.node, "direction": pin.direction,
                "pin_offset": [_exact(pin.dx), _exact(pin.dy)],
                "pin_center": [_exact(x), _exact(y)],
            })
        endpoints[base] = endpoint_records
        x, y = _center(snapshot.nodes, snapshot.placements, base)
        sites.append({"id": f"site:{base}", "x": _scaled(x, snapshot.scale), "y": _scaled(y, snapshot.scale)})
        edges.append({
            "id": base, "source": f"pin:{base}:0", "target": f"pin:{base}:1",
            "base_delay": 0, "alpha": 1, "eligible_sites": list(site_ids),
        })
    source_metadata = dict(source or {})
    manifest = {
        "adapter": _ADAPTER,
        "source": source_metadata,
        "files": snapshot.files,
        "coordinate_scale": snapshot.scale,
        "coordinate_rule": "scale * (placement_lower_left + node_dimension / 2 + pin_offset)",
        "selected_net_ids": list(snapshot.selected),
        "selected_net_count": len(snapshot.selected),
        "total_cross_net_count": len(snapshot.pairs),
        "fixed_cross_net_count": len(snapshot.pairs) - len(snapshot.selected),
        "total_node_count": len(snapshot.nodes),
        "total_split_net_count": len(snapshot.nets),
        "total_pin_count": sum(len(pins) for pins in snapshot.nets.values()),
        "fixed_net_ids": sorted(snapshot.pairs.keys() - set(snapshot.selected)),
        "selection_rule": "all and only paired nets having degree 2 on both split sides; no score-based filtering",
        "position_rule": "permute selected original occupied HBT sites; all other HBTs and all cells remain fixed",
        "objective_semantics": {
            "T": "maximum selected interconnect geometric length; independent one-edge DAGs, not circuit timing",
            "L": "sum of selected split-net HPWL; equals sum of selected source-HBT-target Manhattan lengths",
            "ordering": "lexicographic (T,L)",
        },
        "limitations": [
            "Author-committed intermediate placement snapshot, not an end-to-end placement or timing benchmark.",
            "No inferred circuit timing connectivity, technology delay calibration, TNS, or WNS.",
            "Multi-pin cross-die nets are fixed and excluded from the optimized objective.",
            "Occupied footprints are preserved; die boundaries, routing, spacing rules and legalization are not verified.",
        ],
        "selected_endpoints": endpoints,
    }
    instance = {
        "schema_version": 1, "task_id": "eda_assignment", "instance_id": instance_id,
        "data": {"nodes": nodes, "sites": sites, "edges": edges},
        "provenance": {"adapter": _ADAPTER, "source": source_metadata, "coordinate_scale": snapshot.scale},
    }
    reference_solution = {
        "schema_version": 1, "task_id": "eda_assignment", "instance_id": instance_id,
        "solution": {"assignment": {base: f"site:{base}" for base in snapshot.selected}},
        "provenance": "original Bookshelf HBT assignment; no optimization or imported score claims",
    }
    return {"instance": instance, "reference_solution": reference_solution, "manifest": manifest}


def audit_bookshelf_assignment(
    directory: Path, solution: Mapping[str, Any], *, coordinate_scale: int,
) -> dict[str, Any]:
    """Re-read source files and independently audit pin-bbox HPWL and HBT sites.

    This audit does not import the TaskPack model, its evaluator, or a solver.
    The caller separately binds the solution to the imported instance ID using
    the TaskPack verifier. Candidate-reported scores and metadata are ignored.
    """
    snapshot = _load(Path(directory))
    if isinstance(coordinate_scale, bool) or not isinstance(coordinate_scale, int) or coordinate_scale != snapshot.scale:
        raise ValueError("coordinate_scale must equal the imported minimal integer scale")
    if not isinstance(solution, Mapping):
        raise ValueError("solution must be an object")
    version = solution.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1 or solution.get("task_id") != "eda_assignment":
        raise ValueError("solution must identify schema 1 and task eda_assignment")
    if not isinstance(solution.get("instance_id"), str) or not solution["instance_id"].strip():
        raise ValueError("solution.instance_id must be a nonempty string")
    payload = solution.get("solution")
    assignment = payload.get("assignment") if isinstance(payload, Mapping) else None
    if not isinstance(assignment, Mapping) or assignment.keys() != set(snapshot.selected):
        raise ValueError("assignment must cover exactly all structurally selected cross-die nets")
    allowed_sites = {f"site:{base}": base for base in snapshot.selected}
    used: set[str] = set()
    for site in assignment.values():
        if not isinstance(site, str) or site not in allowed_sites or site in used:
            raise ValueError("assignment must be a capacity-one bijection onto the selected original HBT sites")
        used.add(site)
    original_centers = {
        base: _center(snapshot.nodes, snapshot.placements, base) for base in snapshot.pairs
    }
    candidate_centers = dict(original_centers)
    for base, site in assignment.items():
        candidate_centers[base] = original_centers[allowed_sites[site]]
    preserved = Counter(original_centers.values()) == Counter(candidate_centers.values())
    if not preserved:
        raise ValueError("full original HBT position multiset was not preserved")

    hpwl: dict[str, Fraction] = {}
    for name, pins in snapshot.nets.items():
        points = [_point(snapshot, pin, candidate_centers) for pin in pins]
        xs, ys = zip(*points)
        hpwl[name] = max(xs) - min(xs) + max(ys) - min(ys)
    selected_lengths = {
        base: sum((hpwl[name] for name in snapshot.pairs[base]), Fraction(0))
        for base in snapshot.selected
    }
    total = sum(hpwl.values(), Fraction(0))
    selected_total = sum(selected_lengths.values(), Fraction(0))
    longest = max(selected_lengths.values())
    hbt_ids = sorted(candidate_centers)
    overlaps = 0
    for index, left in enumerate(hbt_ids):
        lx, ly = candidate_centers[left]
        for right in hbt_ids[index + 1:]:
            rx, ry = candidate_centers[right]
            if abs(lx - rx) < (snapshot.nodes[left].width + snapshot.nodes[right].width) / 2 and abs(ly - ry) < (snapshot.nodes[left].height + snapshot.nodes[right].height) / 2:
                overlaps += 1
    return {
        "coordinate_scale": coordinate_scale,
        "objectives": [_scaled(longest, coordinate_scale), _scaled(selected_total, coordinate_scale)],
        "total_split_hpwl": _scaled(total, coordinate_scale),
        "selected_split_hpwl": _scaled(selected_total, coordinate_scale),
        "fixed_split_hpwl": _scaled(total - selected_total, coordinate_scale),
        "hbt_positions_preserved": preserved,
        "hbt_overlap_pairs": overlaps,
        "overlap_rule": "positive-area axis-aligned HBT rectangle overlap; boundary contact excluded",
        "source_units": {
            "objectives": [_exact(longest), _exact(selected_total)],
            "total_split_hpwl": _exact(total),
            "selected_split_hpwl": _exact(selected_total),
            "fixed_split_hpwl": _exact(total - selected_total),
        },
        "selected_net_lengths": {base: _scaled(length, coordinate_scale) for base, length in selected_lengths.items()},
        "split_net_hpwl": {name: _scaled(length, coordinate_scale) for name, length in hpwl.items()},
        "files": snapshot.files,
    }
