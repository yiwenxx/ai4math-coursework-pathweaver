"""Offline task catalogue and EDA generation, solving and verification."""
import argparse

from pathweaver import __version__
from pathweaver.tasks import describe_tasks
from pathweaver.tasks.eda_assignment.cli import add_eda_parser, run_eda_command


def main() -> None:
    parser = argparse.ArgumentParser(description="PathWeaver verifiable optimization prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="Show available public capabilities")
    tasks = sub.add_parser("tasks", help="List public task implementations")
    tasks.add_argument("--json", action="store_true")
    add_eda_parser(sub)
    args = parser.parse_args()
    if args.command == "eda":
        run_eda_command(args, parser)
        return
    if args.command == "info":
        print(f"PathWeaver {__version__}: runnable EDA TaskPack")
        print("Available: instance generation, capacity/eligibility checks, independent (T,L) evaluation, baseline and path-matching strategy.")
        print("Autonomous discovery, other tasks and execution isolation are planned.")
        return
    print(describe_tasks(as_json=args.json))
