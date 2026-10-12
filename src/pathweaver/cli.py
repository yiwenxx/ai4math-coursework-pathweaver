"""Offline public commands; unreleased tasks are absent from the catalogue."""
import argparse

from pathweaver import __version__
from pathweaver.tasks import describe_tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="PathWeaver public development scaffold")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("info", help="Show available public capabilities")
    tasks = sub.add_parser("tasks", help="List public task implementations")
    tasks.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "info":
        print(f"PathWeaver {__version__}: public scaffold")
        print("Available: generic interfaces and offline CLI.")
        print("Search integration and runnable tasks are planned.")
        return
    print(describe_tasks(as_json=args.json))
