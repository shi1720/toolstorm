import asyncio
import json

import pytest

from toolstorm import (
    Cassette,
    ConfigurationError,
    Contract,
    RateLimited,
    RecordedToolError,
    Redactor,
    ReplayMismatch,
    ResponseLost,
    Rule,
    Storm,
    ToolTimeout,
    ToolUnavailable,
    VirtualClock,
)
from toolstorm.cli import main
from toolstorm.demo import POLICIES, SCENARIOS, run_demo
from toolstorm.serialization import REDACTED


def trace():
    storm = Storm(clock=VirtualClock())

    @storm.tool("echo")
    def echo(value=1, *, enabled=True):
        return {"values": [value], "enabled": enabled}

    echo()
    return storm.report().to_dict()


def wrap(replay, name="echo"):
    @replay.tool(name)
    def forbidden(value=1, *, enabled=True):
        raise AssertionError("LIVE FUNCTION CALLED")

    return forbidden


def test_no_live_execution_and_defaults_are_bound():
    with Cassette(trace()).replay() as replay:
        assert wrap(replay)(enabled=True, value=1) == {"values": [1], "enabled": True}


def test_nested_mutable_outputs_do_not_mutate_cassette():
    cassette = Cassette(trace())
    snapshot = cassette.dumps()
    with cassette.replay() as replay:
        wrap(replay)()["values"].append(99)
    assert cassette.dumps() == snapshot
    with cassette.replay() as replay:
        assert wrap(replay)()["values"] == [1]


def test_constructor_and_export_are_detached():
    data = trace()
    cassette = Cassette(data)
    data["calls"][0]["output"]["values"].append(99)
    exported = cassette.to_dict()
    exported["calls"][0]["output"]["values"].append(100)
    assert cassette.to_dict()["calls"][0]["output"]["values"] == [1]


@pytest.mark.parametrize("kwargs", [{"value": True}, {"enabled": 1}, {"value": 1.0}])
def test_bool_int_and_float_distinction(kwargs):
    with pytest.raises(ReplayMismatch), Cassette(trace()).replay() as replay:
        wrap(replay)(**kwargs)


def test_wrong_tool_name():
    with pytest.raises(ReplayMismatch):
        wrap(Cassette(trace()).replay(), "other")()


def test_unused_call():
    with pytest.raises(ReplayMismatch, match="unused"), Cassette(trace()).replay():
        pass


def test_extra_call_and_sticky_failure():
    replay = Cassette(trace()).replay()
    tool = wrap(replay)
    tool()
    with pytest.raises(ReplayMismatch, match="extra"):
        tool()
    with pytest.raises(ReplayMismatch, match="previously diverged"):
        replay.assert_consumed()


def test_wrong_arguments_cannot_be_caught_to_pass():
    replay = Cassette(trace()).replay()
    with pytest.raises(ReplayMismatch):
        wrap(replay)(99)
    with pytest.raises(ReplayMismatch, match="previously diverged"):
        wrap(replay)()


def test_mismatch_does_not_leak_payload(capsys):
    with pytest.raises(ReplayMismatch) as info:
        wrap(Cassette(trace()).replay())("SUPER-SECRET")
    assert "SUPER-SECRET" not in str(info.value)


def test_async_does_not_execute():
    async def scenario():
        storm = Storm(clock=VirtualClock())

        @storm.tool("async_tool")
        async def source(value):
            return {"value": value}

        await source(3)
        with Cassette.from_report(storm.report()).replay() as replay:

            @replay.tool("async_tool")
            async def forbidden(value):
                raise AssertionError("LIVE ASYNC FUNCTION CALLED")

            assert await forbidden(3) == {"value": 3}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "exception",
    [
        ToolTimeout("message"),
        ResponseLost("message"),
        ToolUnavailable("message"),
        RateLimited(0.75),
    ],
)
def test_known_errors_replayed(exception):
    storm = Storm(clock=VirtualClock())

    @storm.tool("fail")
    def source():
        raise exception

    with pytest.raises(type(exception)):
        source()
    with Cassette.from_report(storm.report()).replay() as replay:

        @replay.tool("fail")
        def forbidden():
            raise AssertionError("LIVE FUNCTION CALLED")

        with pytest.raises(type(exception)) as info:
            forbidden()
        if isinstance(exception, RateLimited):
            assert info.value.retry_after == 0.75


def test_unknown_errors_use_safe_standin():
    storm = Storm(clock=VirtualClock())

    @storm.tool("fail")
    def source():
        raise LookupError("DO NOT CAPTURE")

    with pytest.raises(LookupError):
        source()
    cassette = Cassette.from_report(storm.report())
    assert "DO NOT CAPTURE" not in cassette.dumps()
    with cassette.replay() as replay:

        @replay.tool("fail")
        def forbidden():
            raise AssertionError("LIVE FUNCTION CALLED")

        with pytest.raises(RecordedToolError) as info:
            forbidden()
        assert info.value.original_type == "LookupError"


def test_redacted_and_custom_secrets_normalization():
    redactor = Redactor(secrets=("special-token",))
    storm = Storm(clock=VirtualClock(), redactor=redactor)

    @storm.tool("secret")
    def source(payload, api_key="first"):
        return payload

    source({"a": (1, 2), "text": "special-token"})
    with Cassette.from_report(storm.report()).replay(redactor=redactor) as replay:

        @replay.tool("secret")
        def forbidden(payload, api_key="second"):
            raise AssertionError("LIVE FUNCTION CALLED")

        assert forbidden({"text": "special-token", "a": [1, 2]}) == {"a": [1, 2], "text": REDACTED}


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(schema_version=True),
        lambda d: d.update(capture=1),
        lambda d: d.update(seed=True),
        lambda d: d.update(extra=1),
        lambda d: d.update(budget_rejections=-1),
        lambda d: d.update(calls={}),
        lambda d: d["calls"][0].update(id=True),
        lambda d: d["calls"][0].update(id=2),
        lambda d: d["calls"][0].update(ordinal=2),
        lambda d: d["calls"][0].update(tool=""),
        lambda d: d["calls"][0].update(key=""),
        lambda d: d["calls"][0].update(started=True),
        lambda d: d["calls"][0].update(elapsed=-1),
        lambda d: d["calls"][0].update(status="unknown"),
        lambda d: d["calls"][0].update(executed=1),
        lambda d: d["calls"][0].update(capture_error=1),
        lambda d: d["calls"][0].update(fault=3),
        lambda d: d["calls"][0].update(kind="unknown"),
        lambda d: d["calls"][0].update(error={"type": "Error"}),
        lambda d: d["calls"][0].update(arguments=[]),
        lambda d: d["calls"][0].update(status="error", error=None),
        lambda d: d["calls"][0].update(status="error", error={"type": "Err", "message": "SECRET"}),
        lambda d: d["calls"][0].update(status="error", error={"type": ""}),
        lambda d: d["calls"][0].update(status="error", error={"type": "Err", "retry_after": True}),
        lambda d: d.update(effects=[{"name": "write", "key": "x", "call_id": 2, "at": 0}]),
        lambda d: d.update(coverage={"unknown": {"eligible": 1, "triggered": 1}}),
    ],
)
def test_reject_invalid_shapes(mutate):
    data = trace()
    mutate(data)
    with pytest.raises(ConfigurationError):
        Cassette(data)


@pytest.mark.parametrize(
    "text",
    [
        '{"schema_version":1,"schema_version":1}',
        "null",
        "[]",
        "{}",
        "[NaN]",
        "[Infinity]",
        "[1e999]",
        "[" * 1000 + "0" + "]" * 1000,
        '{"x":',
        "\ufeff{}",
    ],
)
def test_bad_json_imports(text):
    with pytest.raises(ConfigurationError):
        Cassette.loads(text)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(capture=False),
        lambda d: d.update(budget_rejections=1),
        lambda d: d["calls"][0].update(status="running"),
        lambda d: d["calls"][0].update(status="cancelled", error={"type": "CancelledError"}),
        lambda d: d["calls"][0].update(capture_error=True),
    ],
)
def test_incomplete_cassette_not_replayable(mutate):
    data = trace()
    mutate(data)
    with pytest.raises(ConfigurationError):
        Cassette(data).replay()


def test_cli_exit_semantics(capsys, tmp_path):
    assert main(["demo", "--scenario", "lost_ack", "--policy", "retry", "--fail-on-contract"]) == 1
    assert (
        main(["demo", "--scenario", "lost_ack", "--policy", "resilient", "--fail-on-contract"]) == 0
    )
    assert main(["demo", "--scenario", "lost_ack", "--policy", "retry"]) == 0
    assert (
        main(
            ["demo", "--scenario", "lost_ack", "--policy", "all", "--cassette", str(tmp_path / "x")]
        )
        == 2
    )
    assert not (tmp_path / "x").exists()
    assert main(["inspect", str(tmp_path / "missing")]) == 2
    assert main(["check", str(tmp_path / "missing")]) == 2


def test_cli_import_invalid_utf8(capsys, tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"\xff")
    assert main(["inspect", str(path)]) == 2


def test_cli_cassette_and_single_run_export(capsys, tmp_path):
    for data in [trace(), run_demo()]:
        path = tmp_path / "trace.json"
        path.write_text(json.dumps(data))
        assert main(["inspect", str(path), "--json"]) == 0
        assert main(["check", str(path), "--max-calls", "0"]) == 1


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("policy", POLICIES)
def test_every_scenario_deterministic(scenario, policy):
    one = run_demo(scenario, policy)
    assert one == run_demo(scenario, policy)
    assert one["stats"]["effects"] == len(one["shipments"])
    assert one["stats"]["calls"] == len(one["report"]["calls"])
    Cassette(one["report"])


def test_empty_contract_cannot_pass():
    report = Storm(clock=VirtualClock()).report()
    contract = Contract(report)
    assert not contract.passed
    with pytest.raises(AssertionError):
        contract.assert_valid()


# Regression candidates: these assert a documented guarantee and currently fail.
@pytest.mark.parametrize("field", ["started", "elapsed"])
def test_huge_json_integer_rejected_as_configuration_error(field):
    data = trace()
    data["calls"][0][field] = 10**400
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_cli_huge_duration_returns_2_without_traceback(capsys, tmp_path):
    data = trace()
    data["calls"][0]["elapsed"] = 10**400
    path = tmp_path / "huge.json"
    path.write_text(json.dumps(data))
    assert main(["inspect", str(path)]) == 2


def test_reject_invented_fault_reference():
    data = trace()
    data["calls"][0].update(fault="invented", kind="timeout")
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_reject_coverage_with_no_supporting_call():
    data = trace()
    data["rules"] = [Rule("not-exercised", "echo", "timeout").to_dict()]
    data["coverage"] = {"not-exercised": {"eligible": 1, "triggered": 1}}
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_read_comparison_output_from_cli(capsys, tmp_path):
    path = tmp_path / "comparison.json"
    assert main(["demo", "--policy", "all", "--output", str(path)]) == 0
    # The reader's comment explicitly claims browser comparison export support.
    assert main(["inspect", str(path), "--json"]) == 0


def test_unknown_error_with_known_short_name_is_not_misclassified():
    # It is not toolstorm.errors.RateLimited, despite the same class name.
    ForeignRateLimited = type("RateLimited", (Exception,), {"__module__": "external_sdk"})
    storm = Storm(clock=VirtualClock())

    @storm.tool("fail")
    def source():
        raise ForeignRateLimited("external SDK retry signal")

    with pytest.raises(ForeignRateLimited):
        source()
    with Cassette.from_report(storm.report()).replay() as replay:

        @replay.tool("fail")
        def forbidden():
            raise AssertionError("LIVE FUNCTION CALLED")

        with pytest.raises(RecordedToolError):
            forbidden()


@pytest.mark.parametrize("scenario", SCENARIOS)
@pytest.mark.parametrize("policy", POLICIES)
def test_swept_demo_honesty_and_budgets(scenario, policy):
    for seed in (-17, 0, 42, 1729):
        for probability in (0.0, 0.5, 1.0):
            for budget in (1, 2, 3, 4, 8, 20):
                result = run_demo(scenario, policy, seed, probability, budget)
                assert len(result["report"]["calls"]) <= budget
                if result["outcome"]["completed"]:
                    assert len(result["shipments"]) >= 1
                    assert result["outcome"]["receipt"] in result["shipments"]
                if policy == "resilient":
                    assert len(result["shipments"]) <= 1
                if scenario == "blackout" and probability == 1:
                    assert result["outcome"]["completed"] is False
                    assert result["shipments"] == []
                if result["contract"]["passed"]:
                    assert len(result["shipments"]) <= 1
                    assert result["stats"]["elapsed"] <= 1.5
                    if scenario != "blackout":
                        assert result["outcome"]["completed"]
                    assert all(c["triggered"] > 0 for c in result["report"]["coverage"].values())


def test_declared_coverage_can_currently_forge_cli_pass(capsys, tmp_path):
    # A genuinely unexercised fault should cause check to fail. Deleting the
    # supporting evidence and altering an aggregate must not silently pass.
    result = run_demo(probability=0)
    assert not result["contract"]["passed"]
    for count in result["report"]["coverage"].values():
        count["triggered"] = 1
    path = tmp_path / "fabricated.json"
    path.write_text(json.dumps(result["report"]))
    assert main(["check", str(path), "--json"]) != 0


@pytest.mark.parametrize(
    "case", ["missing-kind", "wrong-kind", "impossible-execution", "orphan-effect"]
)
def test_reject_contradictory_trace_semantics(case):
    data = run_demo()["report"]
    faulty = next(c for c in data["calls"] if c["fault"])
    if case == "missing-kind":
        faulty["kind"] = None
    elif case == "wrong-kind":
        faulty["kind"] = "rate_limit"
    elif case == "impossible-execution":
        faulty["executed"] = False
    else:
        data["calls"][data["effects"][0]["call_id"] - 1]["executed"] = False
    with pytest.raises(ConfigurationError):
        Cassette(data)
