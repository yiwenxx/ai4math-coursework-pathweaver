"""Recompute saved finite colorings; this does not verify the asymptotic proof."""

import argparse
import json
from pathlib import Path


def integer(value, name, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def labels(row, length, palette):
    colors = row.get("colors")
    if not isinstance(colors, list) or len(colors) != length:
        raise ValueError(f"Expected exactly {length} color labels")
    if any(type(c) is not int or not 0 <= c < palette for c in colors):
        raise ValueError(f"Color labels must be integers in [0,{palette - 1}]")
    return colors


def check_interval(row):
    n = integer(row["n"], "n", 1)
    colors = labels(row, n, n)
    checked = violations = 0
    for d in range(1, (n - 1) // 3 + 1):
        for a in range(n - 3 * d):
            checked += 1
            if len({colors[a + i * d] for i in range(4)}) < 3:
                violations += 1
    return {"kind": "interval", "n": n, "colors": len(set(colors)),
            "checked_progressions": checked, "violations": violations,
            "valid": violations == 0}


def check_cyclic(row):
    m = integer(row["m"], "m", 2)
    r = integer(row["palette_limit"], "palette_limit", 1)
    colors = labels(row, m, r)
    checked = violations = 0
    for a in range(m):
        for d in range(1, m):
            checked += 1
            if (colors[a] == colors[(a + 3 * d) % m]
                    and colors[(a + d) % m] == colors[(a + 2 * d) % m]):
                violations += 1
    return {"kind": "cyclic_ABBA", "m": m, "colors": len(set(colors)),
            "checked_progressions": checked, "violations": violations,
            "valid": violations == 0,
            "crosses_quarter_threshold": violations == 0 and m > len(set(colors)) ** 4}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "research/jsp158/finite-colorings.json")
    args = parser.parse_args()
    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
        if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
            raise ValueError("Expected schema_version=1")
        intervals, templates = data["interval_colorings"], data["cyclic_ABBA_templates"]
        if not isinstance(intervals, list) or not intervals:
            raise ValueError("interval_colorings must be a nonempty list")
        if not isinstance(templates, list) or not templates:
            raise ValueError("cyclic_ABBA_templates must be a nonempty list")
        results = [check_interval(row) for row in intervals]
        results.extend(check_cyclic(row) for row in templates)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.exit(2, f"Invalid artifact: {error}\n")
    print(json.dumps({"results": results,
                      "asymptotic_proof_verified": False,
                      "novelty_verified": False}, indent=2))
    return 0 if all(row["valid"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
