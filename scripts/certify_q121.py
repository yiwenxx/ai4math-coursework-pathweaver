"""Generate and/or independently verify the q=121 mixed-curve witness certificate."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pathweaver.tasks.jsp158_coloring.q121_certificate import (
    generate_certificate,
    load_certificate,
    save_certificate,
    verify_certificate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate and immediately verify the q=121 certificate")
    gen.add_argument("--output", required=True, type=Path)
    ver = sub.add_parser("verify", help="Independently verify an existing q=121 certificate file")
    ver.add_argument("certificate", type=Path)
    args = parser.parse_args()

    if args.command == "generate":
        t0 = time.monotonic()
        cert = generate_certificate()
        t_gen = time.monotonic() - t0
        save_certificate(args.output, cert)
        t1 = time.monotonic()
        verdict = verify_certificate(load_certificate(args.output))
        t_ver = time.monotonic() - t1
        verdict["generate_seconds"] = round(t_gen, 3)
        verdict["verify_seconds"] = round(t_ver, 3)
        verdict["certificate_bytes"] = args.output.stat().st_size
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
    else:
        t1 = time.monotonic()
        verdict = verify_certificate(load_certificate(args.certificate))
        verdict["verify_seconds"] = round(time.monotonic() - t1, 3)
        print(json.dumps(verdict, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
