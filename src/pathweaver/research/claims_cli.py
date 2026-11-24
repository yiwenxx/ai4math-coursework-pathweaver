"""Domain-neutral CLI for inspecting, planning, and compiling Lean blueprints for claim ledgers."""
from pathlib import Path

from pathweaver.core.contracts import read_strict_json, write_json
from pathweaver.research.blueprint import BlueprintCompiler
from pathweaver.research.claims import ClaimLedger
from pathweaver.research.formal_verifier import default_formal_project_dir


def add_claims_parser(subparsers):
    parser = subparsers.add_parser("claims", help="Inspect scoped claim dependency ledgers")
    commands = parser.add_subparsers(dest="claims_command", required=True)
    for name, desc in (
        ("inspect", "Show claim dispositions and dependency impact scores"),
        ("plan", "Compute the next highest-impact audit/formalize/repair/propose work unit"),
        ("blueprint", "Compile a bidirectional Lean formalization blueprint from a claim bundle"),
    ):
        cmd = commands.add_parser(name, help=desc)
        cmd.add_argument("bundle_pos", nargs="?", type=Path, help="Version 1 claim bundle JSON")
        cmd.add_argument("--bundle", dest="bundle_opt", type=Path, help="Version 1 claim bundle JSON")
        if name == "blueprint":
            cmd.add_argument("--formal-dir", type=Path, help="Lean 4 formal directory to scan")
            cmd.add_argument("--mermaid", action="store_true", help="Output Mermaid flowchart instead of JSON")


def run_claims_command(args, parser):
    try:
        if args.bundle_opt is not None and args.bundle_pos is not None:
            if args.bundle_opt.resolve() != args.bundle_pos.resolve():
                raise ValueError("Pass either positional <bundle.json> or --bundle <bundle.json>, not different files")
        raw_bundle = args.bundle_opt or args.bundle_pos
        if raw_bundle is None:
            raise ValueError("Missing claim bundle path (pass <bundle.json> or --bundle <bundle.json>)")
        bundle_path = raw_bundle.resolve()
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
        elif args.claims_command == "blueprint":
            formal_dir = args.formal_dir
            if formal_dir is None:
                local_formal = bundle_path.parent / "formal"
                formal_dir = local_formal if local_formal.is_dir() else default_formal_project_dir()
            compiler = BlueprintCompiler(ledger, formal_dir=formal_dir)
            if args.mermaid:
                print(compiler.to_mermaid(), end="")
            else:
                write_json(compiler.compile())
        else:
            write_json({
                "dispositions": dispositions,
                "impact_scores": impact,
                "next": ledger.plan(set()),
            })
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Claims ledger error: {error}\n")
