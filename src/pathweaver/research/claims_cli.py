"""Domain-neutral CLI for inspecting and planning scoped mathematical claim ledgers."""
from pathlib import Path

from pathweaver.core.contracts import read_strict_json, write_json
from pathweaver.research.claims import ClaimLedger


def add_claims_parser(subparsers):
    parser = subparsers.add_parser("claims", help="Inspect scoped claim dependency ledgers")
    commands = parser.add_subparsers(dest="claims_command", required=True)
    for name, desc in (("inspect", "Show claim dispositions and dependency impact scores"),
                       ("plan", "Compute the next highest-impact audit/formalize/repair/propose work unit")):
        cmd = commands.add_parser(name, help=desc)
        cmd.add_argument("--bundle", required=True, type=Path, help="Version 1 claim bundle JSON")


def run_claims_command(args, parser):
    try:
        bundle_path = args.bundle.resolve()
        ledger = ClaimLedger()
        ledger.apply(read_strict_json(bundle_path), bundle_path.parent)
        dispositions = ledger.dispositions()
        impact = ledger.impact_scores()
        if args.claims_command == "inspect":
            write_json({
                "claim_count": len(ledger.claims),
                "evidence_count": len(ledger.evidence),
                "dispositions": dispositions,
                "impact_scores": impact,
            })
        else:
            write_json({
                "dispositions": dispositions,
                "impact_scores": impact,
                "next": ledger.plan(set()),
            })
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Claims ledger error: {error}\n")
