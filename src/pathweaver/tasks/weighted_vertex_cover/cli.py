"""Offline weighted vertex cover generation, solving and independent verification CLI."""
from dataclasses import asdict
from pathlib import Path

from pathweaver.core.contracts import SolveBudget, read_strict_json, write_json
from . import WeightedVertexCoverTaskPack
from .baseline import exact_solve
from .model import parse_instance


def add_wvc_parser(subparsers):
    parser = subparsers.add_parser("wvc", help="Generate, solve or verify weighted minimum vertex cover")
    commands = parser.add_subparsers(dest="wvc_command", required=True)
    gen = commands.add_parser("generate", help="Generate a seeded weighted vertex cover instance")
    gen.add_argument("--size", type=int, default=16)
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--output", type=Path)
    solve = commands.add_parser("solve", help="Run baseline or tiny exact branch-and-bound solver")
    solve.add_argument("instance", type=Path)
    solve.add_argument("--strategy", choices=("baseline", "exact"), default="baseline")
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--wall-seconds", type=float, default=5.0)
    solve.add_argument("--max-evaluations", type=int, default=1000)
    solve.add_argument("--output", type=Path)
    verify = commands.add_parser("verify", help="Independently verify vertex cover feasibility and weight")
    verify.add_argument("instance", type=Path)
    verify.add_argument("solution", type=Path)


def run_wvc_command(args, parser):
    pack = WeightedVertexCoverTaskPack()
    try:
        if args.wvc_command == "generate":
            write_json(pack.generate(seed=args.seed, size=args.size), args.output)
            return
        instance = read_strict_json(args.instance)
        parse_instance(instance)
        if args.wvc_command == "solve":
            budget = SolveBudget(args.wall_seconds, args.max_evaluations, args.seed)
            sol = exact_solve(instance, budget) if args.strategy == "exact" else pack.baseline(instance, budget)
            write_json(sol, args.output)
            return
        try:
            solution = read_strict_json(args.solution)
        except (ValueError, UnicodeError) as error:
            write_json({"feasible": False, "objectives": None, "violations": [f"invalid solution JSON: {error}"]})
            parser.exit(1)
        result = pack.verify(instance, solution)
        write_json(asdict(result))
        if not result.feasible:
            parser.exit(1)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"WVC input/output error: {error}\n")
