"""CLI for Lean 4 formal verification, certificate export, and ClaimLedger admission."""
import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pathweaver.core.contracts import EvidenceLevel, read_strict_json, write_json
from pathweaver.research.claims import ClaimLedger
from pathweaver.research.formal_verifier import lean_toolchain_status, verify_formal_proof


def add_lean_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "lean",
        help="Inspect Lean 4 toolchain, verify proofs, export task certificates, and admit claims",
    )
    commands = parser.add_subparsers(dest="lean_command", required=True)

    info = commands.add_parser("info", help="Check installed Lean 4 / Lake toolchain and formal project status")
    info.add_argument("--project-dir", type=Path, help="Optional Lake project directory")

    check = commands.add_parser("check", help="Run host Lean 4 kernel verification with zero-sorry and axiom audit")
    check.add_argument("file", type=Path, help="Lean 4 source file (.lean)")
    check.add_argument("--theorem", help="Target theorem name to check with #print axioms")
    check.add_argument("--project-dir", type=Path, help="Optional Lake project directory")
    check.add_argument("--docker-image", help="Optional immutable Docker image for containerized checking")
    check.add_argument("--timeout", type=float, default=60.0)

    verify_inst = commands.add_parser("verify-instance", help="Strictly verify a lean_proof JSON instance and solution")
    verify_inst.add_argument("instance", type=Path)
    verify_inst.add_argument("solution", type=Path)

    export_cert = commands.add_parser(
        "export-cert",
        help="Export an independent EDA, WVC, or JSP-000158 solution/certificate to a Lean 4 proof",
    )
    export_cert.add_argument("--task", choices=("eda", "wvc", "jsp158"), required=True)
    export_cert.add_argument("--instance", required=True, type=Path)
    export_cert.add_argument("--solution", required=True, type=Path)
    export_cert.add_argument("--theorem", help="Custom Lean theorem identifier")
    export_cert.add_argument("--output", type=Path, help="Write generated .lean file instead of stdout")
    export_cert.add_argument("--verify", action="store_true", help="Run Lean 4 kernel verification immediately")
    export_cert.add_argument("--timeout", type=float, default=120.0)

    admit = commands.add_parser(
        "admit-claim",
        help="Verify a Lean 4 proof with the kernel and admit it as `formal_proof` in a ClaimLedger bundle",
    )
    admit.add_argument("--bundle", required=True, type=Path, help="Version 1 claim bundle JSON")
    admit.add_argument("--claim-id", required=True, help="Target claim ID in the bundle")
    admit.add_argument("--file", required=True, type=Path, help="Lean 4 proof file (.lean) relative to bundle root")
    admit.add_argument("--theorem", help="Theorem name to audit via #print axioms")
    admit.add_argument("--project-dir", type=Path, help="Optional Lake project directory")
    admit.add_argument("--evidence-id", help="Evidence record ID (defaults to <claim-id>-lean-<stem>)")
    admit.add_argument("--summary", help="Short summary of the verified Lean theorem")
    admit.add_argument("--timeout", type=float, default=60.0)
    admit.add_argument("--apply", action="store_true", help="Write the new formal_proof entry into --bundle")


def _cmd_check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    source = args.file.read_bytes().decode("utf-8-sig")
    result = verify_formal_proof(
        source, backend="lean4", theorem_name=args.theorem,
        project_dir=args.project_dir, docker_image=args.docker_image, timeout_seconds=args.timeout,
    )
    payload = result.as_dict()
    payload["evidence_level"] = (
        EvidenceLevel.FORMAL_VERIFIED.value if result.status == "verified" else EvidenceLevel.UNVERIFIED.value
    )
    write_json(payload)
    if result.status != "verified":
        parser.exit(1)


def _cmd_verify_instance(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    from pathweaver.tasks.lean_proof import LeanProofTaskPack

    eval_res = LeanProofTaskPack().verify(read_strict_json(args.instance), read_strict_json(args.solution))
    write_json(asdict(eval_res))
    if not eval_res.feasible or eval_res.evidence != EvidenceLevel.FORMAL_VERIFIED:
        parser.exit(1)


def _cmd_export_cert(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    instance = read_strict_json(args.instance)
    solution = read_strict_json(args.solution)
    if args.task == "eda":
        from pathweaver.tasks.eda_assignment.lean_cert import export_eda_lean_certificate
        exported = export_eda_lean_certificate(instance, solution, theorem_name=args.theorem or "eda_finite_optimal")
    elif args.task == "wvc":
        from pathweaver.tasks.weighted_vertex_cover.lean_cert import export_wvc_lean_certificate
        exported = export_wvc_lean_certificate(instance, solution, theorem_name=args.theorem)
    else:
        from pathweaver.tasks.jsp158_coloring.lean_cert import export_jsp158_lean_certificate
        exported = export_jsp158_lean_certificate(instance, solution, theorem_name=args.theorem or "jsp158_four_ap_valid")

    lean_source = exported["lean_source"]
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(lean_source, encoding="utf-8", newline="\n")
    else:
        print(lean_source, end="")

    if args.verify:
        verdict = verify_formal_proof(
            lean_source, backend="lean4", theorem_name=exported["theorem_name"], timeout_seconds=args.timeout,
        )
        summary = {k: v for k, v in exported.items() if k != "lean_source"}
        summary["output"] = str(args.output) if args.output is not None else None
        summary["verification"] = verdict.as_dict()
        summary["evidence_level"] = (
            EvidenceLevel.FORMAL_VERIFIED.value if verdict.status == "verified" else EvidenceLevel.UNVERIFIED.value
        )
        write_json(summary)
        if verdict.status != "verified":
            parser.exit(1)
    elif args.output is not None:
        summary = {k: v for k, v in exported.items() if k != "lean_source"}
        summary["output"] = str(args.output)
        write_json(summary)


def _cmd_admit_claim(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    bundle_path = args.bundle.resolve()
    bundle_root = bundle_path.parent
    proof_path = args.file.resolve()
    if not proof_path.is_relative_to(bundle_root):
        raise ValueError("Lean proof file must reside under the claim bundle directory")
    raw_bytes = proof_path.read_bytes()
    verdict = verify_formal_proof(
        raw_bytes.decode("utf-8-sig"), backend="lean4",
        theorem_name=args.theorem, project_dir=args.project_dir, timeout_seconds=args.timeout,
    )
    if verdict.status != "verified":
        write_json({"admitted": False, "claim_id": args.claim_id, "verification": verdict.as_dict()})
        parser.exit(1)

    bundle = read_strict_json(bundle_path)
    ledger = ClaimLedger()
    ledger.apply(bundle, bundle_root)
    if args.claim_id not in ledger.claims:
        raise ValueError(f"Unknown claim ID in bundle: {args.claim_id!r}")

    theorem_label = args.theorem or "checked_module"
    entry = {
        "id": args.evidence_id or f"{args.claim_id}-lean-{proof_path.stem}",
        "claim_id": args.claim_id,
        "kind": "formal_proof",
        "summary": args.summary or (
            f"Lean 4 kernel verified `{theorem_label}` "
            f"(axioms: {', '.join(verdict.axioms) if verdict.axioms else 'none'})"
        ),
        "source": proof_path.relative_to(bundle_root).as_posix(),
    }
    updated = {
        "schema_version": bundle["schema_version"],
        "claims": list(bundle["claims"]),
        "evidence": [*bundle["evidence"], entry],
    }
    test_ledger = ClaimLedger()
    test_ledger.apply(updated, bundle_root, verify_formal=True)
    if args.apply:
        write_json(updated, bundle_path)
    write_json({
        "admitted": True,
        "applied": bool(args.apply),
        "claim_id": args.claim_id,
        "evidence": entry,
        "claim_disposition": test_ledger.dispositions()[args.claim_id],
        "verification": verdict.as_dict(),
    })


def run_lean_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        if args.lean_command == "info":
            write_json(lean_toolchain_status(args.project_dir))
        elif args.lean_command == "check":
            _cmd_check(args, parser)
        elif args.lean_command == "verify-instance":
            _cmd_verify_instance(args, parser)
        elif args.lean_command == "export-cert":
            _cmd_export_cert(args, parser)
        elif args.lean_command == "admit-claim":
            _cmd_admit_claim(args, parser)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Lean command error: {error}\n")
