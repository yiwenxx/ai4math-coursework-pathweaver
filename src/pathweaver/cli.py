"""Offline public commands; unreleased tasks are absent from the catalogue."""
import argparse
import json
import tomllib
from importlib.resources import files

from pathweaver import __version__


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
    catalogue = tomllib.loads(
        files("pathweaver.tasks").joinpath("catalog.toml").read_text(encoding="utf-8")
    )
    if args.json:
        print(json.dumps(catalogue, ensure_ascii=False, indent=2))
    elif not catalogue["task"]:
        print("No public task implementations have been released.")
    else:
        for task in catalogue["task"]:
            print(f"{task['id']}: {task['title']} [{task['status']}]")
