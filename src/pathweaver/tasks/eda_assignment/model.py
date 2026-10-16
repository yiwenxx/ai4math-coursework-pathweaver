"""Trusted, dependency-free data model for EDA path-coupled assignment."""
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import heapq
from typing import Any


TASK_ID = "eda_assignment"
SCHEMA_VERSION = 1


class InvalidInstanceError(ValueError):
    """The instance is malformed or does not define a supported DAG."""

    def __init__(self, violations: Sequence[str]):
        self.violations = tuple(violations)
        super().__init__("; ".join(self.violations))


class InfeasibleInstanceError(InvalidInstanceError):
    """Eligibility cannot assign a distinct site to every cross-tier edge."""


@dataclass(frozen=True)
class Node:
    id: str
    x: int
    y: int
    tier: int


@dataclass(frozen=True)
class Site:
    id: str
    x: int
    y: int


@dataclass(frozen=True)
class Edge:
    id: str
    source: str
    target: str
    delay: int | None
    base_delay: int
    alpha: int
    eligible_sites: tuple[str, ...]


@dataclass(frozen=True)
class Instance:
    instance_id: str
    nodes: dict[str, Node]
    sites: dict[str, Site]
    edges: tuple[Edge, ...]
    topological_order: tuple[str, ...]

    @property
    def cross_edges(self) -> tuple[Edge, ...]:
        return tuple(
            edge for edge in self.edges
            if self.nodes[edge.source].tier != self.nodes[edge.target].tier
        )


def _integer(value: Any, *, nonnegative: bool = False) -> bool:
    return (
        isinstance(value, int) and not isinstance(value, bool)
        and (not nonnegative or value >= 0)
    )


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unknown_fields(
    record: Mapping[str, Any], allowed: set[str], path: str, violations: list[str],
) -> None:
    for key in sorted(record.keys() - allowed, key=str):
        violations.append(f"{path}: unknown field {key!r}")


def parse_instance(raw: Mapping[str, Any]) -> Instance:
    """Parse schema 1, check acyclicity, and require a complete eligible matching.

    Top-level metadata is allowed but never participates in constraints or scores.
    IDs are preserved verbatim; coordinates may be negative and tied.
    """
    violations: list[str] = []
    if not isinstance(raw, Mapping):
        raise InvalidInstanceError(("instance must be an object",))
    if not _integer(raw.get("schema_version")) or raw["schema_version"] != SCHEMA_VERSION:
        violations.append(f"schema_version must be {SCHEMA_VERSION}")
    if raw.get("task_id") != TASK_ID:
        violations.append(f"task_id must be {TASK_ID!r}")
    instance_id = raw.get("instance_id")
    if not _identifier(instance_id):
        violations.append("instance_id must be a nonempty string")
    data = raw.get("data")
    if not isinstance(data, Mapping):
        raise InvalidInstanceError((*violations, "data must be an object"))
    _unknown_fields(data, {"nodes", "sites", "edges"}, "data", violations)
    collections: dict[str, list[Any]] = {}
    for name in ("nodes", "sites", "edges"):
        value = data.get(name)
        if not isinstance(value, list):
            violations.append(f"data.{name} must be an array")
            collections[name] = []
        else:
            collections[name] = value
    if not collections["nodes"]:
        violations.append("data.nodes must contain at least one node")

    nodes: dict[str, Node] = {}
    sites: dict[str, Site] = {}
    for kind, output in (("nodes", nodes), ("sites", sites)):
        seen: set[str] = set()
        allowed = {"id", "x", "y", "tier"} if kind == "nodes" else {"id", "x", "y"}
        for index, record in enumerate(collections[kind]):
            path = f"data.{kind}[{index}]"
            before = len(violations)
            if not isinstance(record, Mapping):
                violations.append(f"{path} must be an object")
                continue
            _unknown_fields(record, allowed, path, violations)
            identifier = record.get("id")
            if not _identifier(identifier):
                violations.append(f"{path}.id must be a nonempty string")
            elif identifier in seen:
                violations.append(f"{path}.id duplicates {identifier!r}")
            else:
                seen.add(identifier)
            for coordinate in ("x", "y"):
                if not _integer(record.get(coordinate)):
                    violations.append(f"{path}.{coordinate} must be an integer")
            if kind == "nodes" and not _integer(record.get("tier"), nonnegative=True):
                violations.append(f"{path}.tier must be a nonnegative integer")
            if len(violations) == before:
                if kind == "nodes":
                    output[identifier] = Node(identifier, record["x"], record["y"], record["tier"])
                else:
                    output[identifier] = Site(identifier, record["x"], record["y"])

    edges: list[Edge] = []
    seen_edges: set[str] = set()
    for index, record in enumerate(collections["edges"]):
        path = f"data.edges[{index}]"
        before = len(violations)
        if not isinstance(record, Mapping):
            violations.append(f"{path} must be an object")
            continue
        identifier = record.get("id")
        if not _identifier(identifier):
            violations.append(f"{path}.id must be a nonempty string")
        elif identifier in seen_edges:
            violations.append(f"{path}.id duplicates {identifier!r}")
        else:
            seen_edges.add(identifier)
        source, target = record.get("source"), record.get("target")
        valid_endpoints = True
        for name, endpoint in (("source", source), ("target", target)):
            if not _identifier(endpoint) or endpoint not in nodes:
                violations.append(f"{path}.{name} must reference an existing node")
                valid_endpoints = False
        if not valid_endpoints:
            continue
        if nodes[source].tier == nodes[target].tier:
            _unknown_fields(record, {"id", "source", "target", "delay"}, path, violations)
            if not _integer(record.get("delay"), nonnegative=True):
                violations.append(f"{path}.delay must be a nonnegative integer")
            if len(violations) == before:
                edges.append(Edge(identifier, source, target, record["delay"], 0, 0, ()))
        else:
            _unknown_fields(
                record, {"id", "source", "target", "base_delay", "alpha", "eligible_sites"},
                path, violations,
            )
            for field in ("base_delay", "alpha"):
                if not _integer(record.get(field), nonnegative=True):
                    violations.append(f"{path}.{field} must be a nonnegative integer")
            eligible = record.get("eligible_sites")
            if not isinstance(eligible, list):
                violations.append(f"{path}.eligible_sites must be an array")
            else:
                seen_sites: set[str] = set()
                for site in eligible:
                    if not _identifier(site) or site not in sites:
                        violations.append(f"{path}.eligible_sites contains an unknown site {site!r}")
                    elif site in seen_sites:
                        violations.append(f"{path}.eligible_sites duplicates {site!r}")
                    else:
                        seen_sites.add(site)
            if len(violations) == before:
                edges.append(Edge(
                    identifier, source, target, None, record["base_delay"],
                    record["alpha"], tuple(eligible),
                ))
    if violations:
        raise InvalidInstanceError(violations)

    indegree = dict.fromkeys(nodes, 0)
    outgoing: dict[str, list[str]] = {identifier: [] for identifier in nodes}
    for edge in edges:
        indegree[edge.target] += 1
        outgoing[edge.source].append(edge.target)
    ready = [identifier for identifier, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        identifier = heapq.heappop(ready)
        order.append(identifier)
        for target in outgoing[identifier]:
            indegree[target] -= 1
            if indegree[target] == 0:
                heapq.heappush(ready, target)
    if len(order) != len(nodes):
        raise InvalidInstanceError(("data.edges must form a DAG; a directed cycle was found",))
    instance = Instance(instance_id, nodes, sites, tuple(edges), tuple(order))
    if find_matching(instance) is None:
        raise InfeasibleInstanceError((
            "eligibility admits no complete capacity-one matching for all cross-tier edges",
        ))
    return instance


def geometric_length(instance: Instance, edge: Edge, site_id: str) -> int:
    """Manhattan source-to-site plus site-to-target length (tier excluded)."""
    source, target, site = instance.nodes[edge.source], instance.nodes[edge.target], instance.sites[site_id]
    return abs(source.x - site.x) + abs(source.y - site.y) + abs(site.x - target.x) + abs(site.y - target.y)


def find_matching(instance: Instance) -> dict[str, str] | None:
    """Deterministic augmenting-path matching, including Hall-type conflicts.

    The iterative search does not impose a Python recursion-depth limit on the
    number of edges. It finds feasibility only; it does not optimize (T, L).
    """
    cross_edges = sorted(instance.cross_edges, key=lambda edge: (len(edge.eligible_sites), edge.id))
    if len(cross_edges) > len(instance.sites):
        return None
    eligible = {edge.id: sorted(edge.eligible_sites) for edge in cross_edges}
    assignment: dict[str, str] = {}
    occupant: dict[str, str] = {}
    for edge in cross_edges:
        queue = deque([edge.id])
        seen_edges = {edge.id}
        parent: dict[str, str] = {}
        free_site: str | None = None
        while queue and free_site is None:
            current = queue.popleft()
            for site in eligible[current]:
                if site in parent:
                    continue
                parent[site] = current
                if site not in occupant:
                    free_site = site
                    break
                next_edge = occupant[site]
                if next_edge not in seen_edges:
                    seen_edges.add(next_edge)
                    queue.append(next_edge)
        if free_site is None:
            return None
        while free_site is not None:
            current = parent[free_site]
            previous_site = assignment.get(current)
            assignment[current] = free_site
            occupant[free_site] = current
            free_site = previous_site
    return assignment
