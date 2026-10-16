"""Import a public case and compare each bundled strategy once with its reference."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pathweaver.core.contracts import SolveBudget
from pathweaver.tasks.eda_assignment import EdaAssignmentTaskPack, compare_objectives
from pathweaver.tasks.eda_assignment.open3dbench import import_coupled_def
from pathweaver.tasks.eda_assignment.path_matching import solve as path_matching
from pathweaver.tasks.eda_assignment.source_audit import audit_coupled_assignment


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(pack, bundle, solution, output, name):
    evaluation = pack.verify(bundle["instance"], solution)
    write_json(output / f"{name}_evaluation.json", asdict(evaluation))
    require(evaluation.feasible, f"Invalid {name} assignment: {evaluation.violations}")
    audit = audit_coupled_assignment(bundle, solution)
    write_json(output / f"{name}_audit.json", audit)
    require(tuple(audit["objectives"]) == evaluation.objectives,
            f"{name}: TaskPack and source geometry disagree")
    require(audit["capacity_one"] and audit["hbt_positions_preserved"]
            and audit["hbt_overlap_pairs"] == 0,
            f"{name}: capacity or physical geometry check failed")
    return evaluation, audit


def report(output, summary):
    rows = []
    for name, result in summary["outcomes"].items():
        t, length = result.get("objectives") or ("—", "—")
        elapsed = result.get("seconds")
        seconds = "unknown" if elapsed is None else f"{elapsed:.6f}"
        rows.append(f"| {name} | {result['status']} | {t} | {length} | {seconds} |")
    budget = summary["budget"]
    text = (
        f"# Open3DBench {summary['case']} assignment comparison\n\n"
        f"Each strategy was invoked once: seed {budget['seed']}, at most "
        f"{budget['max_evaluations']} full-DAG evaluations and "
        f"{budget['wall_seconds']} cooperative wall seconds.\n\n"
        "| Assignment | Status | T | L | Solve seconds |\n"
        "|---|---|---:|---:|---:|\n" + "\n".join(rows) + "\n\n"
        "Smaller exact (T,L) tuples are better. The published reference is rescored; "
        "its placer runtime is unknown. Import and independent verification are "
        "outside each solver's budget.\n\n"
        "See comparison.json for bounds, exact comparisons and failures, and the "
        "per-assignment files for solutions, evaluations and source geometry audits. "
        "These are geometric proxies, not electrical timing or PPA.\n"
    )
    (output / "report.md").write_text(text, encoding="utf-8")


def run(args, output):
    data = args.data_root
    paths = {
        "def": data / "placements" / f"{args.case}.def",
        "bottom_lef": data / "lef/NangateOpenCellLibrary.macro.mod.bottom.lef",
        "upper_lef": data / "lef/NangateOpenCellLibrary.macro.mod.upper.lef",
        "lib": data / "lib/NangateOpenCellLibrary_typical.lib",
    }
    for path in paths.values():
        if not path.is_file():
            raise ValueError(f"Missing input {path}; see docs/eda_public_cases.md")
    budget = SolveBudget(args.wall_seconds, args.max_evaluations, args.seed)
    print(f"Importing {args.case} and checking coupled paths and site competition...", flush=True)
    bundle = import_coupled_def(paths["def"], [paths["bottom_lef"], paths["upper_lef"]],
                                paths["lib"], instance_id=f"open3dbench-{args.case}")
    for name, value in bundle.items():
        write_json(output / f"{name}.json", value)
    require(bundle["admission"]["accepted"],
            "Input does not meet coupled-path, site-competition or geometry requirements")
    pack = EdaAssignmentTaskPack()
    print("Verifying the public reference...", flush=True)
    reference, source_reference = verify(pack, bundle, bundle["reference_solution"], output, "reference")
    outcomes = {"reference": {"status": "verified", "objectives": reference.objectives,
                              "lower_bound": reference.lower_bound, "seconds": None,
                              "evidence": reference.evidence, "source_audit": source_reference}}
    for name, solver in (("baseline", pack.baseline), ("path-matching", path_matching)):
        print(f"Running {name} once...", flush=True)
        started = perf_counter()
        try:
            solution = solver(bundle["instance"], budget)
        except (TimeoutError, ValueError, TypeError, ArithmeticError, RuntimeError) as error:
            seconds = perf_counter() - started
            outcomes[name] = {"status": "solver_failed", "objectives": None,
                              "seconds": seconds, "error_type": type(error).__name__, "error": str(error)}
            write_json(output / f"{name}_failure.json", outcomes[name])
            continue
        seconds = perf_counter() - started
        write_json(output / f"{name}_solution.json", solution)
        try:
            evaluation, audit = verify(pack, bundle, solution, output, name)
            delta = [new - old for new, old in zip(evaluation.objectives, reference.objectives)]
            require(audit["total_split_hpwl"] - source_reference["total_split_hpwl"] == delta[1],
                    f"{name}: HPWL change disagrees with L change")
        except (ValueError, TypeError, ArithmeticError, RuntimeError) as error:
            outcomes[name] = {"status": "verification_failed", "objectives": None,
                              "seconds": seconds, "error_type": type(error).__name__, "error": str(error)}
            write_json(output / f"{name}_failure.json", outcomes[name])
            continue
        outcomes[name] = {"status": "verified", "objectives": evaluation.objectives,
                          "lower_bound": evaluation.lower_bound, "evidence": evaluation.evidence,
                          "seconds": seconds, "metadata": solution.get("metadata", {}),
                          "source_audit": audit, "minus_reference": delta,
                          "comparison_vs_reference": compare_objectives(evaluation.objectives, reference.objectives)}
    success = all(item["status"] == "verified" for item in outcomes.values())
    manifest = bundle["manifest"]
    summary = {
        "status": "completed" if success else "completed_with_failure", "case": args.case,
        "budget": asdict(budget), "solver_invocations": {"baseline": 1, "path-matching": 1},
        "python": platform.python_version(), "platform": platform.system(),
        "inputs": {name: path.relative_to(data).as_posix() for name, path in paths.items()},
        "counts": {key: manifest[key] for key in ("node_count", "edge_count", "selected_net_count", "total_hbt_count", "fixed_hbt_count")},
        "outcomes": outcomes,
        "comparison_key": {"-1": "better", "0": "equal", "1": "worse"},
        "reference_runtime": "unknown; published assignment rescored, placer not rerun",
    }
    if success:
        summary["path_matching_vs_baseline"] = compare_objectives(
            outcomes["path-matching"]["objectives"], outcomes["baseline"]["objectives"])
    write_json(output / "comparison.json", summary)
    report(output, summary)
    print(f"{summary['status']}: {output / 'report.md'}", flush=True)
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("aes", "ibex"), required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="A new output directory")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-evaluations", type=int, default=1000)
    parser.add_argument("--wall-seconds", type=float, default=30)
    args = parser.parse_args()
    if args.max_evaluations < 1 or not math.isfinite(args.wall_seconds) or args.wall_seconds <= 0:
        parser.error("max-evaluations and finite wall-seconds must be positive")
    output = args.output_dir
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.exit(2, f"Cannot create output directory: {error}\n")
    try:
        code = run(args, output)
    except (OSError, ValueError, TypeError, ArithmeticError, RuntimeError) as error:
        write_json(output / "failure.json", {"status": "run_failed", "error_type": type(error).__name__, "error": str(error)})
        parser.exit(2, f"Comparison failed: {error}\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
