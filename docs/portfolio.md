# ToolStorm: project pitch and demonstration

## One sentence

ToolStorm is a Python testing library that makes agent tools fail predictably and checks what actually happened, including duplicate side effects hidden behind a successful retry.

## The problem

An agent can receive a valid response while doing the wrong thing. A shipping tool may commit a shipment and then lose its acknowledgement. An eager retry creates a second shipment. Tests that only inspect the final response miss the incident.

ToolStorm models the execution boundary explicitly: failures before execution, altered responses, declared latency, and lost responses after success. A test author records the actual commit in an isolated fixture and writes a behavioral contract. Deterministic decisions and portable cassettes make failures repeatable.

## A two-minute demonstration

1. Open the lab on **Lost acknowledgement**. Press **Run comparison**. Python executes locally in a worker.
2. Select **Unchecked retries**. It completes the task but produces two shipments. Open **Checks** to see the failed side-effect assertion.
3. Select **Validated retries**. It reuses an idempotency key and produces one shipment. Open the failed first shipping call to inspect the commit that preceded the lost response.
4. Switch to **Rate limit**. Compare immediate retries with honoring the retry hint. Switch to **Sustained outage** to demonstrate that honest, bounded failure can be the correct outcome.
5. Export a run. Inspect it with the CLI. Show the example that records a cassette, then replays without invoking wrapped live code.

## Engineering discussion

- **Algorithms:** fault decisions hash seed, rule, tool, and invocation identity independently. Adding calls to another tool does not perturb a target tool's schedule.
- **Concurrency:** session counters are protected; context-local state tracks nested calls. Strict replay groups nested descendants in a linear preprocessing pass and locks matching plus consumption to prevent duplicate reads.
- **Debugging:** negative controls distinguish final-response success from correct world state. Reviews uncovered redaction collisions, false coverage, nested replay errors, and a concurrent consumption race; regression tests preserve each fix.
- **Reproducibility:** versioned bounded JSON, a CLI, pytest integration, six deterministic scenarios, and cross-runtime parity checks connect the library to the interactive demonstration.
- **Architecture:** the Python package has no runtime dependencies. The website uses the same source through Pyodide and exposes no arbitrary-code execution endpoint.

## Suggested application description

> ToolStorm — an MIT-licensed Python library and interactive resilience lab for agent tools. It supports deterministic fault injection, explicit side-effect contracts, sync/async tools, bounded replay cassettes, and pytest integration. The demo exposes a duplicate-write bug caused by a lost acknowledgement and verifies an idempotent reference policy. Validation combines adversarial regressions, property tests, a five-version Python CI matrix, cross-runtime checks, and browser tests.

Built with AI assistance and independent agent reviews. The repository contains the implementation, examples, reasoning, limitations, and validation evidence. Review and understand the code before presenting engineering decisions in an interview; it is an initial beta project, not a claim of prior production usage.
