# Positioning, related work, and pitch

## The problem

Agent tooling makes it easy to call APIs and hard to prove what happens when an API partially succeeds. Happy-path checks do not establish that retries are safe. A timeout is especially troublesome around side effects: an action can commit while its response never reaches the caller.

ToolStorm's purpose is to turn a specific failure hypothesis into a small executable regression: inject it at a function boundary, observe real fixture commits, assert the recovery behavior, and retain the observed calls for strict offline replay.

## A 30-second pitch

> ToolStorm is a zero-dependency Python library for testing agents on their bad days. It can drop a tool's acknowledgement after the action actually succeeds, reveal duplicate side effects from naïve retries, and prove that an idempotent recovery fixes the problem. The same engine powers a browser lab, pytest contracts, and portable replay fixtures. It focuses on explicit, reproducible evidence instead of a single opaque resilience score.

## Existing work

This is an established space. ToolStorm does not claim to invent chaos testing, replay, or side-effect evaluation.

- [VCR.py](https://vcrpy.readthedocs.io/en/latest/advanced.html) established HTTP cassette workflows, matching, sensitive-data filters, and replay-consumption controls. ToolStorm operates at Python function boundaries rather than recording HTTP exchanges.
- [Chronicle](https://github.com/theagentplane/chronicle) offers agent boundary capture and replay. ToolStorm's focus is a deliberately small combination of explicit fault phases, actual-trigger coverage, and commit contracts.
- [agent-chaos](https://github.com/deepankarm/agent-chaos) explores tool failures, mutation, scenarios, and report assertions. [agentfuzz](https://github.com/SubhashPavan/agentfuzz) also targets agent fault testing. ToolStorm's framework-neutral function wrappers can be used directly in existing Python tests.
- [AgentChaos](https://github.com/IntelligentDDS/AgentChaos) targets LLM HTTP perturbations and validates injection activity. ToolStorm targets local callable boundaries rather than acting as a model proxy.
- [havoc](https://github.com/bernardobbl/havoc) explores simulated tools, duplicate side effects, and what agents claim versus what occurred. The ambiguous-write problem is important across these systems.

These descriptions reflect primary project documentation inspected during development. They are not benchmark comparisons or claims that other projects lack undocumented features.

## Why build this version?

A team should be able to add a meaningful tool-failure regression without adopting a new agent framework, sending traces to a service, or buying model calls just to test retry code. A small Python API, zero runtime dependencies, readable JSON evidence, and an honest interactive demonstration make that workflow accessible.

The distinguishing combination is intentionally narrow:

1. Before-call versus after-success failure semantics.
2. Separate eligible, selected, and actually triggered fault evidence.
3. Side-effect equality that remains correct under redaction.
4. Fail-closed replay and internally consistent imported traces.
5. One Python implementation for local tests and the public browser lab.

## Engineering evidence for reviewers

The project contains reproducible negative controls, golden recovery behavior, typed sync/async boundaries, deterministic decisions, adversarial regressions, property tests, cross-runtime comparison, and CI. It demonstrates environment construction, defect diagnosis, refactoring, and technical explanation.

It does not claim production adoption, community usage, model benchmark superiority, or professional experience acquired through building this repository. The public project is designed to be inspected and discussed on its actual merits.
