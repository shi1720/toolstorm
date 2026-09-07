"""Properties around observable behavior, independent of presentation details."""

import asyncio
import math
import runpy
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from toolstorm import (
    Cassette,
    ConfigurationError,
    Contract,
    Redactor,
    Rule,
    Storm,
    ToolTimeout,
    VirtualClock,
)
from toolstorm.clock import RealClock, duration
from toolstorm.serialization import canonical


@given(
    seed=st.integers(min_value=-(10**6), max_value=10**6),
    probability=st.floats(min_value=0, max_value=1),
)
@settings(max_examples=100)
def test_other_tools_do_not_perturb_fault_schedule(seed, probability):
    def schedule(interleave):
        storm = Storm(
            [Rule("flaky", "read", "timeout", probability=probability)],
            seed=seed,
            clock=VirtualClock(),
        )

        @storm.tool("read")
        def read(value):
            return value

        @storm.tool("other")
        def other():
            return None

        outcomes = []
        for i in range(20):
            if interleave:
                other()
            try:
                read(i)
                outcomes.append("ok")
            except ToolTimeout:
                outcomes.append("timeout")
        return outcomes

    assert schedule(False) == schedule(True)


json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**63), max_value=2**63)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=30)
)
json_objects = st.recursive(
    json_scalars,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=12), children, max_size=4)
    ),
    max_leaves=20,
)


@given(value=json_objects)
def test_cassette_round_trip_never_calls_live_tool(value):
    storm = Storm(clock=VirtualClock())

    @storm.tool("echo")
    def echo(value):
        return value

    actual = echo(value)
    cassette = Cassette.loads(Cassette.from_report(storm.report()).dumps())
    with cassette.replay() as replay:

        @replay.tool("echo")
        def forbidden(value):
            pytest.fail("A replay reached live code")

        assert canonical(forbidden(value)) == canonical(Redactor().scrub(actual))


@pytest.mark.parametrize(
    "options",
    [
        {"name": ""},
        {"tool": ""},
        {"kind": "unknown"},
        {"calls": (0,)},
        {"calls": (1, 1)},
        {"calls": (True,)},
        {"probability": -1},
        {"probability": 2},
        {"probability": True},
        {"probability": math.nan},
        {"delay": math.inf},
        {"delay": -1},
        {"limit": 0},
        {"limit": True},
    ],
)
def test_bad_rules_fail_before_tool_registration(options):
    defaults = {"name": "fault", "tool": "read", "kind": "timeout"}
    with pytest.raises(ConfigurationError):
        Rule(**(defaults | options))


@pytest.mark.parametrize(
    "options",
    [{"seed": True}, {"seed": 2**60}, {"max_calls": 0}, {"max_calls": 10001}, {"capture": 1}],
)
def test_bad_session_options_rejected(options):
    with pytest.raises(ConfigurationError):
        Storm(**options)


def test_duplicate_rules_rejected():
    with pytest.raises(ConfigurationError):
        Storm([Rule("same", "a", "timeout"), Rule("same", "b", "timeout")])


def test_effect_limits_and_per_tool_calls():
    storm = Storm(clock=VirtualClock())

    @storm.tool("write")
    def write(order):
        storm.effect("receipt", order)
        return None

    write("a")
    write("b")
    Contract(storm.report()).at_most_effects("receipt", 2).at_most_effects(
        "receipt", 1, key="a"
    ).at_most_calls(2, tool="write").assert_valid()
    assert not Contract(storm.report()).at_most_effects("receipt", 1).passed
    for method in (
        lambda: Contract(storm.report()).at_most_calls(-1),
        lambda: Contract(storm.report()).at_most_effects("receipt", -1),
        lambda: Contract(storm.report()).check("x", 1, "invalid"),
    ):
        with pytest.raises(ConfigurationError):
            method()


def test_pytest_fixture_covers_a_real_fault(storm_factory):
    storm = storm_factory([Rule("missing", "get", "timeout")], clock=VirtualClock())

    @storm.tool("get")
    def get():
        pytest.fail("A pre-call timeout executed the tool")

    with pytest.raises(ToolTimeout):
        get()


def test_custom_redaction_collision_is_explicit():
    redactor = Redactor(secrets=("a-secret", "b-secret"))
    with pytest.raises(ConfigurationError):
        redactor.scrub({"a-secret": 1, "b-secret": 2})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 10**400, -1, True])
def test_invalid_clock_values_never_sleep(value):
    with pytest.raises(ConfigurationError):
        duration(value)


def test_real_clock_zero_duration_and_async_virtual_clock():
    real = RealClock()
    before = real.now()
    real.sleep(0)
    assert real.now() >= before
    asyncio.run(real.asleep(0))
    virtual = VirtualClock()
    asyncio.run(virtual.asleep(0.25))
    assert virtual.now() == 0.25


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.py")),
    ids=lambda p: p.stem,
)
def test_documented_examples_execute(path):
    runpy.run_path(str(path), run_name="__main__")


def test_incomplete_output_capture_preserves_tool_result_but_blocks_replay():
    storm = Storm(clock=VirtualClock())

    @storm.tool("get")
    def get():
        return object()

    assert get() is not None
    assert storm.report().calls[0]["capture_error"]
    with pytest.raises(ConfigurationError):
        Cassette.from_report(storm.report()).replay()
