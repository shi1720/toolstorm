# Changelog

## 0.2.0 — 2026-09-07

- Rebuild the browser lab around observed outcomes, policy comparison, and committed-effect evidence. Replace policy nicknames with behavioral descriptions; make timing, provenance, and changed settings explicit.
- Add runnable local commands for the displayed result, readable mobile layouts, no-JavaScript guidance, and refreshed documentation.
- Recreate failed Python workers so transient runtime-download errors can recover. Make cancellation neutral, bound startup to 90 seconds, and reconcile configuration on same-route navigation.
- Reject unreportable replacement configuration before execution. Reserve report-envelope depth when capturing payloads so successful outputs cannot make a report unexportable.
- Reject impossible imported evidence: probability-zero selected faults, replacement payload mismatches, and successful ordinary calls without execution.
- Add regression tests for capture/import boundaries and browser lifecycle failures. Fresh-install both built distributions in CI.


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
