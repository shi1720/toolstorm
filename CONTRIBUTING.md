# Contributing

The most useful contribution is a real failure mode with a test that distinguishes a broken implementation from a corrected one.

## Setup

Use Python 3.10+ and Node 22.13+. Install `pip install -e '.[test]'` in a virtual environment and `npm ci` for the website. The core library has no runtime dependencies. Please do not add a framework dependency for a single integration example.

Before a pull request:

```bash
python -m coverage run --source=toolstorm -m pytest
python -m coverage report --fail-under=90
ruff check src tests examples
mypy src/toolstorm
python scripts/bundle_engine.py
npm run typecheck
npm run lint
npm run test:engine
npm run build
```

The Python-to-browser bundle and initial result are generated files. Edit `src/toolstorm`, then regenerate them. Never hand-edit the browser copy of the engine or the reported fixture results.

## Add a scenario

1. Explain the concrete incident and its pre-/post-execution semantics.
2. Construct a deterministic in-memory fixture; do not call a real paid API in CI.
3. Include a broken control and a corrected control.
4. Verify actual fault coverage and world state, not only the return value.
5. Document the boundary and any facts the harness cannot observe.

Scenarios in `demo.py` are editorial examples, not a benchmark leaderboard. Avoid arbitrary scores, fake traffic numbers, or unverified performance claims.

## API and safety

- Preserve cancellation and original exceptions. Do not put retries inside `Storm`.
- Do not add pickle, `eval`, automatic dynamic exception imports, or live replay fallback.
- Keep redaction and equality semantics explicit; inspect exported artifacts for secrets.
- Do not catch a capture error and invent a replayable success value.
- Update schema/version documentation for incompatible report changes.
- Keep changes focused and include a reproducible regression for defects.

A useful pull request states the problem, changed behavior, validation, and remaining limits. Be considerate in issues and reviews. For security-sensitive reports, follow [SECURITY.md](SECURITY.md).
