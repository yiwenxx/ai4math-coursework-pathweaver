# Contributing

Start with README, STATUS and existing public issues. Small, focused PRs are easiest to assess.

- Describe the public problem and the resulting behavior.
- For behavior changes, explain how to reproduce and validate them.
- Keep task-specific representations behind TaskPack.
- Identify whether evidence is a hypothesis, an observed experiment or a checked certificate.
- Do not include credentials, personal datasets or material you cannot redistribute.

Default local validation is source compilation and a wheel build:

```bash
python -m compileall -q src scripts
python -m pip wheel . --no-deps --wheel-dir dist
```

CI runs the same compilation and build. Additional tests should address a concrete behavior or failure.
