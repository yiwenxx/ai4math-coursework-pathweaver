"""Offline EDA generation, baseline solving and independent JSON verification."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from pathweaver.core.contracts import SolveBudget

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


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _read_json(path: Path) -> Any:
    # Repeated assignment keys must not silently disappear during JSON decoding.
    return json.loads(path.read_text(encoding="utf-8-sig"),
                      object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _write_json(value: Any, path: Path | None = None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path is None:
        print(text, end="")
    else:
        path.write_text(text, encoding="utf-8")


def run_eda_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    pack = EdaAssignmentTaskPack()
    try:
        if args.eda_command == "generate":
            _write_json(pack.generate(seed=args.seed, size=args.size), args.output)
        elif args.eda_command == "solve":
            instance = _read_json(args.instance)
            budget = SolveBudget(wall_seconds=args.wall_seconds,
                                 max_evaluations=args.max_evaluations, seed=args.seed)
            if args.strategy == "path-matching":
                from .path_matching import solve

                solution = solve(instance, budget)
            else:
                solution = pack.baseline(instance, budget)
            _write_json(solution, args.output)
        else:
            instance = _read_json(args.instance)
            # Diagnose the instance before attempting to decode candidate output.
            from .model import parse_instance

            parse_instance(instance)
            try:
                solution = _read_json(args.solution)
            except (ValueError, UnicodeError) as error:
                _write_json({"feasible": False, "objectives": None,
                             "violations": [f"invalid solution JSON: {error}"],
                             "diagnostics": {"failure_kind": "invalid_solution"},
                             "lower_bound": None, "evidence": "experimental"})
                parser.exit(1)
            result = pack.verify(instance, solution)
            _write_json(asdict(result))
            if not result.feasible:
                parser.exit(1)
    except InfeasibleInstanceError as error:
        parser.exit(2, f"Infeasible EDA instance: {error}\n")
    except InvalidInstanceError as error:
        parser.exit(2, f"Invalid EDA instance: {error}\n")
    except TimeoutError as error:
        parser.exit(3, f"EDA baseline timed out: {error}\n")
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"EDA input/output error: {error}\n")
