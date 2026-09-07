"""Adversarial behavioral cases for the framework-neutral boundary engine."""

import asyncio

import pytest

from toolstorm import (
    BudgetExceeded,
    ConfigurationError,
    Contract,
    RateLimited,
    Redactor,
    ResponseLost,
    Rule,
    Storm,
    ToolTimeout,
    ToolUnavailable,
    VirtualClock,
)
from toolstorm.serialization import REDACTED, canonical


@pytest.mark.parametrize(
    ("kind", "exception"),
    [("timeout", ToolTimeout), ("rate_limit", RateLimited), ("unavailable", ToolUnavailable)],
)
def test_pre_execution_faults_never_commit(kind, exception):
    storm = Storm([Rule("failure", "charge", kind, delay=2)], clock=VirtualClock())
    ledger = []

    @storm.tool()
    def charge():
        ledger.append("paid")
        storm.effect("charge", "order-1")
        return {"paid": True}

    with pytest.raises(exception):
        charge()
    report = storm.report()
    assert ledger == []
    assert report.effects == []
    assert report.calls[0]["executed"] is False
    assert report.calls[0]["status"] == "error"


def test_lost_acknowledgement_commits_once_and_preserves_evidence():
    storm = Storm([Rule("failure", "charge", "response_lost")], clock=VirtualClock())
    ledger = []

    @storm.tool()
    def charge():
        ledger.append("paid")
        storm.effect("charge", "order-1")
        return {"paid": True}

    with pytest.raises(ResponseLost):
        charge()
    report = storm.report()
    assert ledger == ["paid"]
    assert len(report.effects) == 1
    assert report.calls[0]["executed"] is True
    assert report.calls[0]["output"] is None
    assert report.calls[0]["error"] == {"type": "ResponseLost", "known": True}


def test_lost_acknowledgement_does_not_mask_real_tool_exception():
    storm = Storm([Rule("failure", "charge", "response_lost")], clock=VirtualClock())
    problem = LookupError("sensitive exception message")

    @storm.tool()
    def charge():
        raise problem

    with pytest.raises(LookupError) as info:
        charge()
    assert info.value is problem
    report = storm.report()
    assert report.calls[0]["error"] == {"type": "LookupError", "known": False}
    assert "sensitive exception message" not in canonical(report.to_dict())


def test_replace_is_not_a_live_write_and_returns_detached_json():
    replacement = {"paid": False, "items": []}
    storm = Storm([Rule("failure", "charge", "replace", replacement=replacement)])

    @storm.tool()
    def charge():
        pytest.fail("replacement must never call the live function")

    replacement["paid"] = True
    returned = charge()
    returned["items"].append(3)
    report = storm.report()
    assert report.calls[0]["output"] == {"paid": False, "items": []}
    assert report.calls[0]["executed"] is False
    assert charge() == {"paid": False, "items": []}


def test_nested_calls_restore_outer_effect_context_even_on_inner_failure():
    storm = Storm(clock=VirtualClock())

    @storm.tool()
    def inner():
        storm.effect("inner", "i")
        raise ValueError("recoverable")

    @storm.tool()
    def outer():
        storm.effect("outer-before", "o")
        with pytest.raises(ValueError):
            inner()
        storm.effect("outer-after", "o")

    outer()
    assert [(e["name"], e["call_id"]) for e in storm.report().effects] == [
        ("outer-before", 1),
        ("inner", 2),
        ("outer-after", 1),
    ]
    with pytest.raises(ConfigurationError):
        storm.effect("outside", "bad")


def test_nested_storms_do_not_share_active_call_or_invocation_key():
    a, b = Storm(clock=VirtualClock()), Storm(clock=VirtualClock())

    @b.tool("same")
    def b_tool():
        b.effect("b", "key")

    @a.tool("same")
    def a_tool():
        b_tool()
        a.effect("a", "key")

    with a.invocation("only-a"):
        a_tool()
    assert a.report().calls[0]["key"] == "only-a"
    assert b.report().calls[0]["key"] == "#1"
    assert a.report().effects[0]["name"] == "a"
    assert b.report().effects[0]["name"] == "b"


def test_async_cancellation_is_not_an_error_or_a_success():
    async def scenario():
        storm = Storm()
        ready = asyncio.Event()

        @storm.tool()
        async def blocked():
            ready.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(blocked())
        await ready.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        report = storm.report()
        assert report.calls[0]["status"] == "cancelled"
        assert report.calls[0]["executed"] is True
        with pytest.raises(ConfigurationError):
            storm.effect("outside", "bad")

    asyncio.run(scenario())


def test_cancellation_during_latency_never_executes_tool():
    class BlockingClock:
        def __init__(self):
            self.ready = asyncio.Event()

        def now(self):
            return 0.0

        async def asleep(self, seconds):
            self.ready.set()
            await asyncio.Event().wait()

    async def scenario():
        clock = BlockingClock()
        storm = Storm([Rule("slow", "write", "latency", delay=1)], clock=clock)

        @storm.tool()
        async def write():
            pytest.fail("cancelled latency must not execute a write")

        task = asyncio.create_task(write())
        await clock.ready.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert storm.report().calls[0]["status"] == "cancelled"
        assert storm.report().calls[0]["executed"] is False

    asyncio.run(scenario())


def test_same_seed_and_explicit_keys_ignore_unrelated_tool_and_schedule_order():
    def execute(order, noise):
        storm = Storm([Rule("coin", "lookup", "timeout", probability=0.5)], seed=981)

        @storm.tool()
        def lookup():
            return True

        @storm.tool()
        def other():
            return "noise"

        decisions = {}
        for key in order:
            if noise:
                other()
            with storm.invocation(key):
                try:
                    lookup()
                    decisions[key] = False
                except ToolTimeout:
                    decisions[key] = True
        return decisions

    order = [f"request-{i}" for i in range(100)]
    baseline = execute(order, False)
    assert set(baseline.values()) == {True, False}
    assert baseline == execute(list(reversed(order)), True)


def test_rule_limit_counts_actual_triggers_and_reports_shadowed_eligibility():
    storm = Storm(
        [
            Rule("first", "tool", "timeout", probability=1, limit=1),
            Rule("second", "tool", "replace", replacement="fallback"),
        ]
    )

    @storm.tool()
    def tool():
        return "live"

    with pytest.raises(ToolTimeout):
        tool()
    assert tool() == "fallback"
    assert storm.report().coverage == {
        "first": {"eligible": 2, "selected": 1, "triggered": 1},
        "second": {"eligible": 2, "selected": 1, "triggered": 1},
    }


def test_defaults_and_keyword_order_are_bound_before_capture():
    storm = Storm()

    @storm.tool()
    def tool(a, /, b=2, *rest, c=4, **other):
        return a + b + c

    assert tool(1) == 7
    assert tool(1, c=4, b=2) == 7
    report = storm.report()
    assert report.calls[0]["arguments"] == report.calls[1]["arguments"]
    assert report.calls[0]["arguments"] == {
        "a": 1,
        "b": 2,
        "rest": [],
        "c": 4,
        "other": {},
    }
    with pytest.raises(TypeError):
        tool(a=1)
    assert len(storm.report().calls) == 2


@pytest.mark.parametrize("output", [object(), "x" * 130_000, float("nan")])
def test_output_capture_failure_does_not_repeat_or_fail_committed_write(output):
    storm = Storm()
    ledger = []

    @storm.tool()
    def write():
        ledger.append(1)
        storm.effect("write", "one")
        return output

    assert write() is output
    assert ledger == [1]
    report = storm.report()
    assert report.calls[0]["status"] == "ok"
    assert report.calls[0]["capture_error"] is True
    assert report.calls[0]["output"] is None


def test_no_capture_supports_non_json_arguments_and_results():
    storm = Storm(capture=False)
    sentinel = object()

    @storm.tool()
    def identity(value):
        return value

    assert identity(sentinel) is sentinel
    assert storm.report().calls[0]["arguments"] is None
    assert storm.report().calls[0]["output"] is None


def test_reports_are_detached_from_future_execution_and_external_mutation():
    storm = Storm()

    @storm.tool()
    def read():
        return {"items": [1, 2]}

    read()
    first = storm.report()
    first.calls[0]["output"]["items"].append(3)
    read()
    second = storm.report()
    assert len(first.calls) == 1
    assert len(second.calls) == 2
    assert second.calls[0]["output"] == {"items": [1, 2]}


def test_call_budget_contract_includes_rejected_attempts():
    storm = Storm(max_calls=1)

    @storm.tool()
    def read():
        return 1

    read()
    with pytest.raises(BudgetExceeded):
        read()
    contract = Contract(storm.report()).at_most_calls(1)
    assert contract.passed is False
    with pytest.raises(AssertionError):
        contract.assert_valid()


def test_empty_or_unexercised_contract_cannot_establish_correctness():
    empty = Contract(Storm().report())
    assert empty.passed is False
    with pytest.raises(AssertionError):
        empty.assert_valid()
    unseen = Contract(Storm([Rule("never", "missing", "timeout")]).report())
    unseen.require_triggered()
    assert unseen.passed is False
    with pytest.raises(AssertionError):
        unseen.assert_valid()


def test_sensitive_values_and_headers_are_scrubbed_without_mutation():
    source = {
        "Authorization": "Bearer abc",
        "set-cookie": "session=abc",
        "nested": [
            {"Api-Key": "abc"},
            "prefix abc suffix",
            {"nonsecret": "safe"},
        ],
    }
    before = canonical(source)
    result = Redactor(secrets=("abc",)).scrub(source)
    assert result == {
        "Authorization": REDACTED,
        "set-cookie": REDACTED,
        "nested": [
            {"Api-Key": REDACTED},
            "prefix [REDACTED] suffix",
            {"nonsecret": "safe"},
        ],
    }
    assert canonical(source) == before
