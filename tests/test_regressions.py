"""Regression tests for defects found during independent adversarial review."""

import asyncio
import sys

import pytest

from toolstorm import ConfigurationError, Contract, Redactor, Storm
from toolstorm.serialization import canonical


def test_literal_secrets_are_removed_from_dictionary_keys():
    redactor = Redactor(secrets=("sk-private-123",))
    payload = {"request sk-private-123": {"safe": 1}}
    assert "sk-private-123" not in canonical(redactor.scrub(payload))


def test_literal_secret_in_nested_dictionary_key_cannot_escape_report():
    storm = Storm(redactor=Redactor(secrets=("sk-private-123",)))

    @storm.tool()
    def search():
        return {"results": [{"sk-private-123": "account metadata"}]}

    search()
    assert "sk-private-123" not in canonical(storm.report().to_dict())


def test_background_task_cannot_log_effect_after_wrapped_call_has_finished():
    async def scenario():
        storm = Storm()
        gate = asyncio.Event()
        children = []

        async def late_commit():
            await gate.wait()
            storm.effect("late-commit", "same-order")

        @storm.tool()
        async def start_background():
            children.append(asyncio.create_task(late_commit()))
            return {"scheduled": True}

        await start_background()
        assert storm.report().calls[0]["status"] == "ok"
        gate.set()
        with pytest.raises(ConfigurationError):
            await children[0]

    asyncio.run(scenario())


def test_contract_does_not_false_pass_for_redacted_effect_name():
    storm = Storm(redactor=Redactor(secrets=("customer-private",)))

    @storm.tool()
    def write_twice():
        storm.effect("charge/customer-private", "order-1")
        storm.effect("charge/customer-private", "order-1")

    write_twice()
    contract = Contract(storm.report()).at_most_effects("charge/customer-private", 1)
    assert contract.passed is False


def test_contract_does_not_false_pass_for_redacted_effect_key():
    storm = Storm(redactor=Redactor(secrets=("customer-private",)))

    @storm.tool()
    def write_twice():
        storm.effect("charge", "customer-private")
        storm.effect("charge", "customer-private")

    write_twice()
    contract = Contract(storm.report()).at_most_effects("charge", 1, key="customer-private")
    assert contract.passed is False


def test_redaction_does_not_merge_distinct_effect_identities():
    storm = Storm(redactor=Redactor(secrets=("private-a", "private-b")))

    @storm.tool()
    def write():
        storm.effect("charge", "private-a")
        storm.effect("charge", "private-b")

    write()
    assert Contract(storm.report()).no_duplicate_effects().passed is True


@pytest.mark.skipif(
    not hasattr(sys, "get_int_max_str_digits"), reason="CPython digit limit unavailable"
)
def test_huge_integer_capture_failure_does_not_change_committed_result():
    storm = Storm()
    result = 10 ** (sys.get_int_max_str_digits() + 100)
    ledger = []

    @storm.tool()
    def commit():
        ledger.append("committed")
        return result

    assert commit() is result
    assert ledger == ["committed"]
    assert storm.report().calls[0]["status"] == "ok"
    assert storm.report().calls[0]["capture_error"] is True


def test_post_call_fault_is_not_exercised_when_underlying_tool_fails():
    from toolstorm import Contract, Rule, Storm, VirtualClock

    storm = Storm([Rule("lost", "save", "response_lost")], clock=VirtualClock())

    @storm.tool("save")
    def save():
        raise ValueError("database refused the write")

    with pytest.raises(ValueError):
        save()
    assert storm.report().coverage["lost"] == {"eligible": 1, "selected": 1, "triggered": 0}
    assert not storm.report().calls[0]["injected"]
    with pytest.raises(AssertionError):
        Contract(storm.report()).require_triggered().assert_valid()


def test_nested_capture_replays_at_outer_boundary_without_live_execution():
    from toolstorm import Cassette, VirtualClock

    storm = Storm(clock=VirtualClock())

    @storm.tool("inner")
    def inner(value):
        return value + 1

    @storm.tool("outer")
    def outer(value):
        return inner(value) * 2

    assert outer(5) == 12
    calls = storm.report().calls
    assert [c["parent_id"] for c in calls] == [None, 1]
    with Cassette.from_report(storm.report()).replay() as replay:

        @replay.tool("outer")
        def forbidden(value):
            pytest.fail("Outer live function executed")

        assert forbidden(5) == 12


@pytest.mark.parametrize("kwargs", [{"missing": 1}, {"value": object()}])
def test_unbindable_or_unserializable_replay_call_is_sticky(kwargs):
    from toolstorm import Cassette, ReplayMismatch, VirtualClock

    storm = Storm(clock=VirtualClock())

    @storm.tool("echo")
    def echo(value=1):
        return value

    echo()
    replay = Cassette.from_report(storm.report()).replay()
    replay_echo = replay.tool("echo")(echo)
    with pytest.raises(ReplayMismatch):
        replay_echo(**kwargs)
    with pytest.raises(ReplayMismatch):
        replay_echo()


@pytest.mark.parametrize("kind", ["timeout", "rate_limit", "unavailable"])
def test_import_cannot_rewrite_injected_error_into_success(kind):
    from toolstorm import Cassette, Rule, ToolError, VirtualClock

    storm = Storm([Rule("bad", "read", kind)], clock=VirtualClock())

    @storm.tool("read")
    def read():
        return 1

    with pytest.raises(ToolError):
        read()
    data = storm.report().to_dict()
    data["calls"][0].update(status="ok", error=None, output=1)
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_rate_limit_negative_control_rejects_immediate_retries():
    from toolstorm.demo import run_demo

    fast = run_demo("rate_limit", "retry")
    safe = run_demo("rate_limit", "resilient")
    assert fast["outcome"]["completed"] and not fast["contract"]["passed"]
    assert safe["contract"]["passed"]
    assert (
        next(c for c in fast["contract"]["checks"] if c["name"] == "Retry-after respected")[
            "passed"
        ]
        is False
    )
