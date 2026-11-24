"""Minimal, focused CLI: task packs, claims ledger, Lean 4 verification, and optional discovery."""
import argparse

from pathweaver import __version__
from pathweaver.research.claims_cli import add_claims_parser, run_claims_command
from pathweaver.research.lean_cli import add_lean_parser, run_lean_command
from pathweaver.tasks import describe_tasks
from pathweaver.tasks.eda_assignment.cli import add_eda_parser, run_eda_command
from pathweaver.tasks.jsp158_coloring.cli import add_jsp158_parser, run_jsp158_command
from pathweaver.tasks.weighted_vertex_cover.cli import add_wvc_parser, run_wvc_command

try:
    from pathweaver.research.discovery_cli import add_discovery_parsers, run_discovery_command
except ImportError:
    add_discovery_parsers = None
    run_discovery_command = None


def main() -> None:
    parser = argparse.ArgumentParser(description="PathWeaver: streamlined verifiable AI4Math discovery core")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="Show core capabilities")
    task_parser = sub.add_parser("tasks", help="List implemented mathematical task packs")
    task_parser.add_argument("--json", action="store_true")
    add_eda_parser(sub)
    add_wvc_parser(sub)
    add_jsp158_parser(sub)
    add_claims_parser(sub)
    add_lean_parser(sub)
    if add_discovery_parsers is not None:
        add_discovery_parsers(sub)
    args = parser.parse_args()
    if args.command in {"discover", "resume"} and run_discovery_command is not None:
        run_discovery_command(args, parser)
        return
    dispatch = {
        "eda": run_eda_command,
        "wvc": run_wvc_command,
        "jsp158": run_jsp158_command,
        "claims": run_claims_command,
        "lean": run_lean_command,
    }
    handler = dispatch.get(args.command)
    if handler is not None:
        handler(args, parser)
        return
    if args.command == "info":
        print(f"PathWeaver {__version__}: streamlined verifiable AI4Math core")
        print("Tasks: eda (primal-dual/Hall finite_optimal certificates), wvc (transfer pack + exact solver), jsp158 (4-AP verifier + PatternBoost + ff_probe + q=121 certificate), lean_proof (warm Lean 4 LSP + Apollo repair + premise retrieval).")
        print("Core: MAP-Elites exact integer-tuple + Pareto ordering, ddmin & active adversarial selector, LRAT/VIPR/Nullstellensatz certificate hub, causal epistemic memory, ClaimLedger/Blueprint, and metamorphic + sealed validation gates.")
        return
    print(describe_tasks(as_json=args.json))
