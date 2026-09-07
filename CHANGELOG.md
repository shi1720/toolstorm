# Changelog

## 0.1.0 — 2026-09-07

Initial beta release.

- Framework-neutral synchronous/asynchronous fault wrappers.
- Six fault kinds with explicit pre-call, replacement, delay, and post-success semantics.
- Stable keyed fault decisions; separate eligibility, selection, and actual injection coverage.
- Explicit side-effect evidence and contracts resistant to redaction identity collisions.
- Bounded JSON cassettes, semantic validation, and strict offline replay.
- pytest fixture, CLI, four executable examples, and six bundled incident recipes.
- Interactive browser lab executing the same Python package through Pyodide.
- Adversarial regressions, property tests, cross-runtime checks, and GitHub Actions.

The API is beta. Streaming, generators, HTTP interception, and framework-specific adapters are outside this release.
