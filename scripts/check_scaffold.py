"""Build preparation: compile parent sources, not upstream checkouts."""
import compileall
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if not compileall.compile_dir(root / "src", quiet=1):
    raise SystemExit("Python compilation failed")
print("Parent sources compiled; mathematical/runtime behavior is not tested.")
