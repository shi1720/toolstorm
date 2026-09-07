# Python API reference

## `Rule(name, tool, kind, *, calls=(), probability=1, limit=None, delay=0, replacement=None)`

The dataclass accepts positional or keyword fields. `name` is a unique stable identifier. `tool` is a case-sensitive glob. `calls` contains unique positive 1-based **per-tool** ordinals. An empty sequence means every ordinal. Probability must be finite in `[0,1]`. `limit` caps rule **selections**; a post-call selection might not actually trigger if the tool itself raises. `delay` is in seconds.

| kind | Tool runs? | Observation |
| --- | --- | --- |
| `timeout` | No | `ToolTimeout` before execution. Does not wait for `delay`. |
| `rate_limit` | No | `RateLimited(retry_after=delay)`. No automatic sleep. |
| `unavailable` | No | `ToolUnavailable`. |
| `replace` | No | A detached copy of `replacement`. |
| `latency` | Once, after delay | Original value or exception. |
| `response_lost` | Once | After a successful return, raise `ResponseLost`. Original tool exceptions propagate. |

Rules support `to_dict()` / `Rule.from_dict(data)` for JSON-based scenarios. Unknown fields and invalid configurations are rejected. First eligible probability hit wins; other eligible rules still receive eligibility evidence.

## `Storm(rules=(), *, seed=0, clock=None, max_calls=1000, capture=True, redactor=None)`

One instance per run. Seeds are integers within `±(2**53 - 1)`. `max_calls` is 1–10,000. The default clock is `RealClock`. `tool(name=None)` returns a decorator preserving the original signature and synchronous/asynchronous form. Pass plain functions or bound methods; generators and callable instances are rejected. Bound methods whose bound arguments include non-JSON objects need `capture=False` or an explicit JSON-oriented function boundary.

```python
wrapped = storm.tool("search")(search)

with storm.invocation("request-17:attempt-1"):
    result = wrapped(query="hello")
```

`invocation()` binds a stable probability key. Each key is unique per tool per run. Do not reuse a key across retry attempts unless the attempts wrap different tools. The application's idempotency key and the harness invocation key have different purposes: a retry should keep the former stable and distinguish the latter.

`effect(name, key)` records an actual commit from inside a currently executing wrapped tool. Both identifiers are nonempty strings up to 200 characters. The same `(name, key)` identifies the same logical effect. Logging an effect after the parent wrapper finishes raises `ConfigurationError`.

`report()` returns a detached `Report`. Wait for concurrent tasks to finish first. `report.to_dict()` exports schema v1 JSON. `report.digest` is SHA-256 of the canonical export, including timing. Deterministic virtual-clock runs have stable digests; real-clock runs generally do not.

Call budgets reject excess attempts **before execution**, count them in `budget_rejections`, and avoid growing a refusal trace indefinitely.

## `Contract(report)`

Chain methods; they return the same contract. `passed` is false for an empty contract. `assert_valid()` raises `AssertionError` with every failing check. `to_dict()` includes named checks and evidence.

- `require_triggered(*names)`: every named rule must have actually fired. No names means every configured rule. Unknown names fail.
- `no_duplicate_effects()`: checks opaque effect equality identities; redaction cannot merge distinct effects.
- `at_most_calls(count, tool=None)`: count recorded attempts, plus refused attempts when checking globally. Refused calls lack per-tool attribution, so per-tool checks count recorded calls only.
- `at_most_effects(name, count, key=None)`: bound matching commits. Fails closed when identities were redacted.
- `check(name, passed, detail)`: add an application-specific boolean assertion. Caller-authored detail text is not automatically redacted.

An absent effect can make an upper-bound check pass. Pair it with a task-completion or minimum-world-state assertion when success is required. A contract only establishes the conditions you explicitly checked.

## Clocks

`RealClock.now()` uses monotonic time; `sleep(seconds)` and `asleep(seconds)` wait. `VirtualClock` accumulates requested durations without wall-clock waiting and yields once during async sleep. It does not model overlapping concurrent time or impose live tool timeouts.

## Cassettes

`Cassette.from_report(report)`, `.loads(text)`, `.load(path)`, `.to_dict()`, `.dumps()`, `.save(path)`, and `.replay(redactor=None)` support capture and strict replay. Use replay as a context manager or call `assert_consumed()` explicitly. See [replay.md](replay.md) for full matching semantics.

## Errors

`ConfigurationError`, `BudgetExceeded`, and `ReplayMismatch` are harness errors, not retryable tool faults. `ToolTimeout`, `RateLimited`, `ToolUnavailable`, and `ResponseLost` represent injected failures. `RecordedToolError` is the safe replay fallback for unknown exception classes. Exception messages are not recorded.

## pytest fixture

Install `toolstorm` with pytest available and pytest discovers the `storm_factory` plugin. `storm_factory(rules, require_triggered=True, **storm_options)` creates an isolated run. Teardown checks actual fault coverage. Set `require_triggered=False` only for tests which deliberately permit unexercised rules.

## Capture limits

Payloads reserve three levels for the report envelope: up to 29 nested levels and 128 KB per capture. Uncapturable return values still reach the caller and set `capture_error`; invalid captured arguments fail before execution. Replacement configurations must be capturable when constructing a Storm, including when call capture is disabled. Full artifacts have separate size limits; see [replay.md](replay.md).
