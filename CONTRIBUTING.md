# Contributing

Start with README, STATUS and existing public issues. Small, focused PRs are easiest to assess.

- Describe the public problem and the resulting behavior.
- For behavior changes, explain how to reproduce and validate them.
- Keep task-specific representations behind TaskPack.
- Identify whether evidence is a hypothesis, an observed experiment or a checked certificate.
- Do not include credentials, personal datasets or material you cannot redistribute.

Maintainers update the public content inventory when preparing a delivery. A content-inventory mismatch in a contribution is expected until that refresh; it should not be bypassed.

Default local validation is source compilation and a wheel build:

```bash
python scripts/check_scaffold.py
python -m pip wheel . --no-deps --wheel-dir dist
```

CI also checks the prepared public file inventory. Additional tests should address a concrete behavior or failure.
