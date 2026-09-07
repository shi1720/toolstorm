# Capture, privacy, and strict replay

## Capture

`Storm(capture=True)` records redacted signature-bound arguments and returned JSON values. Redaction uses common credential keys plus optional literal secrets:

```python
from toolstorm import Redactor, Storm

storm = Storm(redactor=Redactor(
    keys=("customer_email",),
    secrets=("literal-test-credential",),
))
```

Credential key matching ignores case and treats hyphens like underscores. Literal secrets are scrubbed from values and dictionary keys. A key collision caused by redaction fails capture explicitly instead of dropping a field. Capturing never mutates the original input or output. Exception messages and tracebacks are omitted.

This is not a general PII or secret detector. Keep rule/tool names and invocation/effect identifiers nonsecret. A secret in free-form text needs an explicit literal filter. Disable payload capture for sensitive or non-JSON tools: `Storm(capture=False)`. This disables replay. Inspect any exported artifact before sharing it.

Limits: 32 JSON nesting levels, 128 KB per captured payload, 8 MB per loaded cassette, at most 10,000 calls and 10,000 effects, and at most 100 rules. These are bounds, not a claim that every maximum-size combination is cheap. A complete large report can exceed the cassette limit; reduce payloads or capture fewer calls.

If **output** capture cannot serialize a successful result, the wrapper returns the original value and sets `capture_error`. Replay rejects it rather than substituting an invented result. Malformed captured arguments fail before the tool runs. `Cassette.save()` uses an atomic replace and owner-readable temporary file on platforms that implement those permissions.

## Matching

Replay matches the next recorded tool name and canonical arguments after binding the replay function's signature and defaults. Pass the same `Redactor` used for capture. Positional and keyword forms compare equally; bool, int, and float forms remain distinct. Tuples normalize to lists. Redacted credentials intentionally lose distinctions.

```python
with cassette.replay(redactor=redactor) as replay:
    wrapped = replay.tool("search")(search_function)
    wrapped(query="resilience")
```

The wrapped `search_function` does not execute. Its signature describes how arguments bind. Replay returns a fresh copy of the recorded output or raises a supported recorded failure. Unsupported third-party exceptions become `RecordedToolError(original_type)`; they cannot be relied on to activate the same exception-specific recovery branches as the original SDK class.

Only exact ToolStorm `ToolTimeout`, `RateLimited`, `ToolUnavailable`, and `ResponseLost` types retain their types. A foreign class with the same short name remains foreign. Known rate limits retain `retry_after`.

## Nested boundaries

A captured call records its `parent_id`. Replaying an outer boundary consumes its recorded nested subtree because the outer implementation does not execute. Other interleaved top-level calls remain pending. Only the replayed outer arguments are matched in that case; the nested entries are retained evidence, not independently re-executed assertions. To test inner call changes, replay at the inner boundary instead of wrapping the outer workflow.

Join nested asynchronous work before the parent returns. Imported traces reject child calls extending beyond a completed parent. Replay preserves invocation order between top-level boundaries; it does not simulate the original completion schedule.

## Failure behavior

- Extra calls, wrong names, or changed arguments raise `ReplayMismatch`.
- A mismatch is sticky: catching it does not make the replay valid.
- Leaving a replay context normally with unused entries raises `ReplayMismatch`.
- Incomplete, cancelled, uncaptured, capture-failed, or budget-refused recordings cannot replay.
- Unknown schema versions, duplicate object keys, NaN/Infinity, malformed structure, inconsistent coverage, or invalid effect linkage fail loading.
- A replay never falls through to wrapped live code and never dynamically imports or evaluates classes named by a file.

No live fallback applies only to decorated boundaries. The rest of the program still executes normally and could perform unwrapped I/O. Replay is not a process sandbox. Recorded effects are evidence, not instructions to mutate a ledger. Tests needing a simulated world should manage that world explicitly.

## Inspect a browser export

```bash
toolstorm inspect toolstorm-lost_ack-retry.json --json
toolstorm check toolstorm-lost_ack-retry.json --max-calls 8
```

`inspect` and `check` accept a standalone cassette, a single exported demo run, or a comparison containing multiple runs. For comparisons, JSON summaries contain a `runs` array. `check` recomputes fault coverage, duplicate-effect and call-budget contracts from the trace; it does not trust the exported UI verdict or verify arbitrary application completion.

CLI exit codes: **0** successful inspection/check, **1** a failed checked contract, **2** invalid arguments or input. `demo` returns 0 even for an intentionally failing negative control unless `--fail-on-contract` is supplied. `--cassette` requires one policy, not `all`.

Internally consistent JSON can still be fabricated. A digest identifies report bytes; it is neither a signature nor proof of execution.
