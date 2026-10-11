"""Check the prepared public file inventory without exposing private metadata."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
inventory = json.loads((root / "PUBLICATION.json").read_text(encoding="utf-8"))
if inventory["schema_version"] != 1:
    raise SystemExit("Unsupported public inventory version")
expected = inventory["files"]
listed = subprocess.run(
    ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    check=True, capture_output=True,
).stdout.decode("utf-8").split("\0")
actual = {name for name in listed if name}
if actual != set(expected) | {"PUBLICATION.json"}:
    raise SystemExit("Public file set does not match the prepared inventory")
for name, digest in expected.items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise SystemExit(f"Invalid public path: {name}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"Public content changed: {name}")
print(f"Public inventory verified: {len(expected)} files.")
