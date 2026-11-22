"""One fixed diagnostic, two unchanged solver calls and a six-assignment oracle."""
import argparse
from collections import Counter
from dataclasses import asdict
from itertools import permutations
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pathweaver.core.contracts import SolveBudget, write_json as _write_json
from pathweaver.tasks.eda_assignment import EdaAssignmentTaskPack
from pathweaver.tasks.eda_assignment.path_matching import solve as path_matching

BUDGET = SolveBudget(wall_seconds=30, max_evaluations=1000, seed=0)
INSTANCE = ROOT / "benchmarks/eda_assignment/coupled_capacity_gap.json"
EDGE_IDS = ("e1", "e2", "e3")


def write_json(path, value):
    _write_json(value, path)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def enumerate_exact(instance):
    """Independent raw-coordinate calculation for this fixture's two paths only.

    Does not call either solver, the TaskPack scorer or its geometric helpers.
    This is deliberately not a general-purpose exact EDA solver.
    """
    data = instance["data"]
    nodes = {node["id"]: node for node in data["nodes"]}
    sites = {site["id"]: site for site in data["sites"]}
    edges = {edge["id"]: edge for edge in data["edges"]}
    require(set(nodes) == {"a0", "a1", "a2", "b0", "b1"}
            and set(edges) == set(EDGE_IDS) and len(sites) == 3,
            "Exact reference is scoped to the three-edge diagnostic")
    require([(edges[e]["source"], edges[e]["target"]) for e in EDGE_IDS]
            == [("a0", "a1"), ("a1", "a2"), ("b0", "b1")],
            "The exact reference requires paths e1,e2 and e3")
    lengths, delays = {}, {}
    for name, edge in edges.items():
        left, right = nodes[edge["source"]], nodes[edge["target"]]
        require(left["tier"] != right["tier"], "All diagnostic edges must cross tiers")
        lengths[name] = {}
        delays[name] = {}
        for site_id in edge["eligible_sites"]:
            site = sites[site_id]
            length = sum(abs(left[axis] - site[axis]) + abs(site[axis] - right[axis])
                         for axis in ("x", "y"))
            lengths[name][site_id] = length
            delays[name][site_id] = edge["base_delay"] + edge["alpha"] * length
    rows = []
    for selected in permutations(sorted(sites), 3):
        assignment = dict(zip(EDGE_IDS, selected))
        if not all(site in lengths[edge] for edge, site in assignment.items()):
            continue
        first = sum(delays[edge][assignment[edge]] for edge in ("e1", "e2"))
        second = delays["e3"][assignment["e3"]]
        rows.append({"assignment": assignment, "path_delays": [first, second],
                     "objectives": [max(first, second),
                                    sum(lengths[e][assignment[e]] for e in EDGE_IDS)]})
    require(len(rows) == 6, "This fixture must have exactly six legal assignments")
    optimum = min(row["objectives"] for row in rows)
    relaxed = [max(min(delays["e1"].values()) + min(delays["e2"].values()),
                   min(delays["e3"].values())),
               sum(min(lengths[e].values()) for e in EDGE_IDS)]
    minimum_length = min(row["objectives"][1] for row in rows)
    return {"method": "exhaustive injective assignments; raw geometry and explicit two-path formula",
            "enumerated_assignments": len(rows), "lengths": lengths, "delays": delays,
            "relaxed_lower_bound": relaxed, "optimal_objectives": optimum,
            "optimal_assignments": [row for row in rows if row["objectives"] == optimum],
            "minimum_length_assignments": [row for row in rows if row["objectives"][1] == minimum_length],
            "assignments": rows}


def verify(pack, instance, solution, exact, output, name):
    evaluation = pack.verify(instance, solution)
    write_json(output / f"{name}_evaluation.json", asdict(evaluation))
    require(evaluation.feasible, f"Invalid {name}: {evaluation.violations}")
    assignment = solution["solution"]["assignment"]
    row = next((row for row in exact["assignments"] if row["assignment"] == assignment), None)
    require(row is not None and tuple(row["objectives"]) == evaluation.objectives,
            f"{name}: independent exact reference disagrees")
    relaxed_lb = tuple(evaluation.diagnostics.get("relaxed_lower_bound", evaluation.lower_bound))
    require(tuple(exact["relaxed_lower_bound"]) == relaxed_lb,
            f"{name}: independent relaxed bound disagrees")
    require(evaluation.lower_bound[0] >= relaxed_lb[0] and evaluation.lower_bound[0] <= evaluation.objectives[0],
            f"{name}: certified lower bound out of sound range")
    loads = Counter(assignment.values())
    return {"objectives": evaluation.objectives, "path_delays": row["path_delays"],
            "feasible": evaluation.feasible, "assigned_edges": len(assignment),
            "distinct_sites": len(loads), "maximum_site_load": max(loads.values()),
            "lower_bound": evaluation.lower_bound, "taskpack_evidence": evaluation.evidence,
            "matches_exact_optimum": list(evaluation.objectives) == exact["optimal_objectives"]}


def run(output):
    instance = json.loads(INSTANCE.read_text(encoding="utf-8"))
    pack = EdaAssignmentTaskPack()
    require(not pack.validate_instance(instance), "Invalid diagnostic instance")
    write_json(output / "instance.json", instance)
    exact = enumerate_exact(instance)
    write_json(output / "exact_reference.json", exact)
    require(exact["relaxed_lower_bound"] == [8, 8] and exact["optimal_objectives"] == [10, 18],
            "Fixture does not have the analytically derived capacity gap")
    require(all(row["objectives"] == [14, 14] for row in exact["minimum_length_assignments"]),
            "Initial minimum-length matching is not the intended diagnostic")
    reference = {key: instance[key] for key in ("schema_version", "task_id", "instance_id")}
    reference["solution"] = {"assignment": exact["optimal_assignments"][0]["assignment"]}
    write_json(output / "exact_solution.json", reference)
    outcomes = {"exact": verify(pack, instance, reference, exact, output, "exact")}
    for name, solver in (("baseline", pack.baseline), ("path-matching", path_matching)):
        print(f"Running {name} once: seed=0, max_evaluations=1000, wall_seconds=30", flush=True)
        started = perf_counter()
        solution = solver(instance, BUDGET)
        seconds = perf_counter() - started
        write_json(output / f"{name}_solution.json", solution)
        result = verify(pack, instance, solution, exact, output, name)
        result.update(seconds=seconds, metadata=solution["metadata"])
        outcomes[name] = result
    trace = outcomes["path-matching"]["metadata"]["trace"]
    require(trace and all(item["objectives"] in [row["objectives"] for row in exact["assignments"]]
                          for item in trace), "Trace contains an impossible objective pair")
    initial, final = trace[0]["objectives"], list(outcomes["path-matching"]["objectives"])
    summary = {"status": "completed", "case": instance["instance_id"], "budget": asdict(BUDGET),
               "solver_invocations": {"baseline": 1, "path-matching": 1},
               "exact_assignments_enumerated": exact["enumerated_assignments"],
               "oracle_and_verification_outside_solver_budget": True,
               "outcomes": outcomes, "initial_path_matching_objectives": initial,
               "later_search_improved": final < initial,
               "accepted_later_phases": [item["phase"] for item in trace[1:] if item["accepted"]],
               "limitations": ["One hand-authored structural diagnostic, no case or seed sweep.",
                               "No solver changes or oracle/reference input to either solver.",
                               "Exact reference is specific to this small fixture; not a scale or physical EDA result."]}
    write_json(output / "comparison.json", summary)
    rows = []
    for name, result in outcomes.items():
        t, length = result["objectives"]
        evaluations = result.get("metadata", {}).get("evaluations", "six enumerated assignments")
        rows.append(f"| {name} | {t} | {length} | {evaluations} | {result['matches_exact_optimum']} |")
    report = ("# Coupled capacity-gap diagnostic\n\n"
              "Seed 0, at most 1000 full-DAG evaluations and 30 cooperative wall seconds per strategy.\n"
              "Each solver was called once. Exact enumeration and verification are separate.\n\n"
              "| Method | T | L | Evaluations | Matches exact optimum |\n"
              "|---|---:|---:|---|---|\n" + "\n".join(rows)
              + f"\n\nRelaxed bound: (8,8). Initial path-matching score: {initial}.\n"
              + f"Later search improved: {summary['later_search_improved']}. "
              + f"Accepted later phases: {summary['accepted_later_phases']}.\n\n"
              + "See exact_reference.json for all six assignments and comparison.json for complete traces.\n")
    (output / "report.md").write_text(report, encoding="utf-8")
    print(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new directory")
    output = parser.parse_args().output_dir
    output.mkdir(parents=True, exist_ok=False)
    try:
        run(output)
    except Exception as error:
        write_json(output / "failure.json", {"error_type": type(error).__name__, "error": str(error)})
        raise


if __name__ == "__main__":
    main()
