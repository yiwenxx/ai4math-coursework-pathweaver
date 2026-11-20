"""Offline EDA generation, baseline solving and independent JSON verification."""
import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pathweaver.core.contracts import SolveBudget, read_strict_json, write_json

from . import EdaAssignmentTaskPack
from .model import InvalidInstanceError, InfeasibleInstanceError


def add_eda_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser("eda", help="Generate, solve or independently verify EDA assignments")
    commands = parser.add_subparsers(dest="eda_command", required=True)
    generate = commands.add_parser("generate", help="Generate a reproducible feasible DAG instance")
    generate.add_argument("--seed", type=int, default=0)
    generate.add_argument("--size", type=int, default=6, help="Number of cross-tier edges")
    generate.add_argument("--output", type=Path, help="Write UTF-8 JSON instead of stdout")
    solve = commands.add_parser("solve", help="Run the built-in baseline without model calls")
    solve.add_argument("instance", type=Path)
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--max-evaluations", type=int, default=1000)
    solve.add_argument("--wall-seconds", type=float, default=5.0)
    solve.add_argument("--strategy", choices=("baseline", "path-matching"), default="baseline",
                       help="Keep the original baseline or use capacity/path-guided minimum-cost matching")
    solve.add_argument("--output", type=Path, help="Write UTF-8 JSON instead of stdout")
    verify = commands.add_parser("verify", help="Recompute feasibility and exact (T, L) from JSON")
    verify.add_argument("instance", type=Path)
    verify.add_argument("solution", type=Path)
    verify.add_argument("--require-certificate", action="store_true",
                        help="Also require an independently verified matching optimality certificate")


def run_eda_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    pack = EdaAssignmentTaskPack()
    try:
        if args.eda_command == "generate":
            write_json(pack.generate(seed=args.seed, size=args.size), args.output)
        elif args.eda_command == "solve":
            instance = read_strict_json(args.instance)
            budget = SolveBudget(wall_seconds=args.wall_seconds,
                                 max_evaluations=args.max_evaluations, seed=args.seed)
            if args.strategy == "path-matching":
                from .path_matching import solve

                solution = solve(instance, budget)
            else:
                solution = pack.baseline(instance, budget)
            write_json(solution, args.output)
        else:
            instance = read_strict_json(args.instance)
            from .model import parse_instance

            parse_instance(instance)
            try:
                solution = read_strict_json(args.solution)
            except (ValueError, UnicodeError) as error:
                write_json({"feasible": False, "objectives": None,
                            "violations": [f"invalid solution JSON: {error}"],
                            "diagnostics": {"failure_kind": "invalid_solution"},
                            "lower_bound": None, "evidence": "experimental"})
                parser.exit(1)
            result = pack.verify(instance, solution)
            write_json(asdict(result))
            if (not result.feasible or (args.require_certificate and
                    result.diagnostics.get("optimality_certificate", {}).get("status") != "verified")):
                parser.exit(1)
    except InfeasibleInstanceError as error:
        parser.exit(2, f"Infeasible EDA instance: {error}\n")
    except InvalidInstanceError as error:
        parser.exit(2, f"Invalid EDA instance: {error}\n")
    except TimeoutError as error:
        parser.exit(3, f"EDA baseline timed out: {error}\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"EDA input/output error: {error}\n")
