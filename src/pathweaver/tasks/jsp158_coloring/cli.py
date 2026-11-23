"""Streamlined JSP-000158 CLI: instance generation, legal seed and independent 4-AP verification."""
from dataclasses import asdict
from pathlib import Path

from pathweaver.core.contracts import SolveBudget, parse_strict_json, read_strict_json, write_json

from . import Jsp158ColoringTaskPack
from .cyclic import MAX_TEMPLATE_BYTES, MAX_TEMPLATE_SIZE, verify_template
from .digit_lift import verify_digit_lift
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
    for name, help_text in (
        ("verify-template", "Check cyclic ABBA or three-color separation and the digit-lift threshold"),
        ("verify-digit-lift", "Check ABBA separation for integer digit products of every length"),
    ):
        template = commands.add_parser(name, help=help_text)
        template.add_argument("template", type=Path, help=(
            f"JSON object with colors or palettes of length 2 to {MAX_TEMPLATE_SIZE}, at most {MAX_TEMPLATE_BYTES} bytes"
        ))
        if name == "verify-template":
            template.add_argument("--three-colors", action="store_true", help=(
                "Require at least three labels on every nonzero-step cyclic four-term progression"
            ))


def run_jsp158_command(args, parser):
    pack = Jsp158ColoringTaskPack()
    try:
        if args.jsp158_command == "generate":
            write_json(pack.generate(seed=args.seed, size=args.size), args.output)
        elif args.jsp158_command in ("verify-template", "verify-digit-lift"):
            try:
                with args.template.open("rb") as source:
                    raw = source.read(MAX_TEMPLATE_BYTES + 1)
                if len(raw) > MAX_TEMPLATE_BYTES:
                    raise ValueError(f"template exceeds {MAX_TEMPLATE_BYTES} bytes")
                template = parse_strict_json(raw.decode("utf-8-sig"))
                if args.jsp158_command == "verify-template":
                    result = verify_template(template, three_colors=getattr(args, "three_colors", False))
                else:
                    result = verify_digit_lift(template)
            except (ValueError, RecursionError) as error:
                write_json({"valid": False, "improves_quarter_via_lift": False,
                            "improves_five_over_twenty_one_via_lift": False, "error": str(error)})
                parser.exit(1)
            write_json(result)
            if not result["valid"]:
                parser.exit(1)
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
