# Changelog

## Unreleased

- Record one successful end-to-end AES comparison through the public entrypoint,
  including exact objectives, capacity checks and runtime counts. No solver code changed.
- Record one successful Ibex comparison through the same entrypoint and budget,
  distinguishing 1592 assigned data-graph edges from 1599 physical HBTs. No code changed.

## 0.1.0.dev1 — 2026-10-16

- Publish the runnable EDA TaskPack with strict JSON formats, global capacity checks,
  independent full-DAG `(T,L)` evaluation and three handwritten examples.
- Provide the original matching/local-search baseline and opt-in path-guided
  minimum-cost matching, plus `eda generate`, `solve` and `verify` commands.
- Publish Open3DBench and Bookshelf adapters, independent source geometry checks,
  AES/Ibex result summaries, and a direct-from-input-files comparison script.
- Document objective semantics, reproduction steps and the limits of transfer evidence.

## 0.1.0.dev0 — 2026-10-11

- Establish the public project with task/evaluation contracts, an offline CLI,
  status, roadmap, contribution guidance and compilation/build CI.

This remains a research prototype. No autonomous discovery or broad superiority is claimed.
