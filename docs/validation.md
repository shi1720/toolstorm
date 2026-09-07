# Validation evidence and practical limits

The release is checked at three layers: library behavior, identical engine execution across runtimes, and the public user flow. Tests are reproducible from the repository; this document describes their scope, not a universal safety certification.

## Python tests

The pytest suite includes independent adversarial reproductions and property-based tests. It covers:

- pre-call faults with zero live executions;
- post-success acknowledgement loss with an actual committed effect;
- original tool exceptions and cancellation propagation;
- nested context restoration and independent sessions;
- stable keyed decisions without cross-tool PRNG coupling;
- actual fault coverage, including selected-but-untriggered post-call rules;
- redaction in nested values and keys, key collisions, and effect equality;
- capture failure preserving a successful live result;
- strict replay matching, no live fall-through, unused/extra/sticky mismatches;
- nested boundary replay and portable-versus-foreign exception identity;
- malformed, overlarge, nonfinite, and internally inconsistent cassettes;
- CLI exit semantics and browser-export inspection;
- all four runnable examples.

The demo sweep tests **1,296 configurations**: six scenarios × three policies × four seeds × three probabilities × six call budgets. It checks world-state honesty, bounded calls, completion claims, no duplicate effects for the resilient policy, and the implications of passing contracts. Hypothesis adds generated schedule and JSON round-trip cases.

```bash
python -m coverage run --source=toolstorm -m pytest
python -m coverage report --fail-under=90
ruff check src tests examples
mypy src/toolstorm
```

The CI matrix targets Python 3.10, 3.11, 3.12, 3.13, and 3.14. The coverage gate is 90% statement coverage. Coverage measures exercised lines, not correctness by itself.

## Cross-runtime parity

`npm run test:engine` loads the generated browser package into Pyodide and compares it against CPython across **36 configurations × 3 policies**. Comparison includes calls, outcomes, effects, contracts, coverage, timings, and digests. It also verifies that every bundled source module and the initial UI fixture match the Python source.

The browser uses this same package in a Web Worker. No TypeScript implementation duplicates fault-selection logic. The initial page is a labeled recorded example; an interactive run is labeled only after the worker returns an executed result.

## Browser flow

The Playwright suite exercises real Python initialization, negative and corrected controls, call details, JSON export contents, scenario selection, query parameters, changed-configuration warnings, zero-probability fault coverage, documentation navigation, and a 390px mobile viewport. It checks critical/serious WCAG A/AA findings with axe and records screenshots/traces on failures.

Browser tests run in GitHub Actions; manual desktop and mobile checks use the same visible browser app. A clean browser test does not prove accessibility for every assistive technology or prove every browser/runtime combination.

## Independent review changes

Reviewers found and reproduced defects before release. Fixes are retained as regression tests, including:

1. Literal secrets in dictionary keys bypassed redaction.
2. Redacted identities made effect assertions falsely pass or conflate distinct effects.
3. A detached async child could report an effect after its parent returned.
4. Very large numeric values escaped normalized validation errors.
5. Imported coverage aggregates could contradict call evidence.
6. A foreign exception named `RateLimited` was misclassified.
7. Comparison exports could not round-trip through CLI inspection.
8. A post-call rule counted as triggered even if the tool itself failed first.
9. Nested wrapped calls were not consumed naturally during outer-boundary replay.
10. Rate-limit tests did not initially assert advertised backoff.

These are concrete defects addressed during development, not independent certification or a claim that no defects remain.

## Limits of the evidence

- The bundled policies are deterministic Python callers, not LLM agents. No model benchmark or provider integration is claimed.
- Virtual timing is a fixture model, not a performance measurement.
- Side effects are explicitly instrumented, not automatically discovered.
- A trace validator checks internal consistency, not authenticity or the original execution environment.
- The public website needs the pinned Pyodide CDN on first run.
- Vinext is a beta framework. The Python package is independent of the website stack.
- Test dependencies are version-ranged; the website uses a committed lockfile. CI runs on hosted images whose underlying system packages may evolve.

Refer to the linked GitHub Actions run for the exact release commit and job results. A successful build or coverage threshold alone should never be described as proof of production maturity.
