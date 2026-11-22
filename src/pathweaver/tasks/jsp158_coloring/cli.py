"""Streamlined JSP-000158 CLI: instance generation, legal seed and independent 4-AP verification."""
from dataclasses import asdict
from pathlib import Path

from pathweaver.core.contracts import SolveBudget, read_strict_json, write_json

from . import Jsp158ColoringTaskPack
from .model import MAX_N, parse_instance


def add_jsp158_parser(subparsers):
    parser = subparsers.add_parser("jsp158", help="Construct or verify finite JSP-000158 four-term AP colorings")
    commands = parser.add_subparsers(dest="jsp158_command", required=True)
    generate = commands.add_parser("generate", help="Create the full interval [1,N] instance")
    generate.add_argument("--size", type=int, default=32, help=f"Interval length N, at most {MAX_N}")
    generate.add_argument("--seed", type=int, default=0, help="Instance label only; N fixes the mathematics")
    generate.add_argument("--output", type=Path)
    solve = commands.add_parser("solve", help="Run the legal recoloring seed without model calls")
    solve.add_argument("instance", type=Path)
    solve.add_argument("--seed", type=int, default=0)
    solve.add_argument("--wall-seconds", type=float, default=5.0)
    solve.add_argument("--max-evaluations", type=int, default=10000, help="Maximum recoloring proposals")
    solve.add_argument("--output", type=Path)
    verify = commands.add_parser("verify", help="Independently enumerate every four-term AP")
    verify.add_argument("instance", type=Path)
    verify.add_argument("solution", type=Path)


def run_jsp158_command(args, parser):
    pack = Jsp158ColoringTaskPack()
    try:
        if args.jsp158_command == "generate":
            write_json(pack.generate(seed=args.seed, size=args.size), args.output)
        else:
            instance = read_strict_json(args.instance)
            parse_instance(instance)
            if args.jsp158_command == "solve":
                budget = SolveBudget(args.wall_seconds, args.max_evaluations, args.seed)
                write_json(pack.baseline(instance, budget), args.output)
            else:
                try:
                    solution = read_strict_json(args.solution)
                except (ValueError, UnicodeError) as error:
                    write_json({"feasible": False, "objectives": None,
                                "violations": [f"invalid solution JSON: {error}"]})
                    parser.exit(1)
                result = pack.verify(instance, solution)
                write_json(asdict(result))
                if not result.feasible:
                    parser.exit(1)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"JSP-000158 input/output error: {error}\n")
