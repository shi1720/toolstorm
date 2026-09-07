import asyncio
import copy
import random
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from threading import Barrier, BrokenBarrierError

import pytest

from toolstorm import (
    Cassette,
    ConfigurationError,
    RecordedToolError,
    Redactor,
    ReplayMismatch,
    Storm,
    VirtualClock,
)


def interleaved_capture():
    async def capture():
        storm = Storm(clock=VirtualClock())
        started = {name: asyncio.Event() for name in ("a", "b")}
        gates = {name: asyncio.Event() for name in ("a", "b")}

        @storm.tool("leaf")
        async def leaf(name):
            return {"leaf": name}

        @storm.tool("child")
        async def child(name):
            started[name].set()
            await gates[name].wait()
            return await leaf(name)

        @storm.tool("root")
        async def root(name):
            first = await child(name)
            second = await leaf(name + "-second")
            return [first, second]

        @storm.tool("independent")
        async def independent():
            return {"independent": True}

        a = asyncio.create_task(root("a"))
        await started["a"].wait()
        b = asyncio.create_task(root("b"))
        await started["b"].wait()
        gates["a"].set()
        av = await a
        gates["b"].set()
        bv = await b
        iv = await independent()
        return storm.report(), [av, bv, iv]

    return asyncio.run(capture())


def test_actual_nested_async_interleaving():
    report, outputs = interleaved_capture()
    assert [(c["id"], c["parent_id"]) for c in report.calls] == [
        (1, None),
        (2, 1),
        (3, None),
        (4, 3),
        (5, 2),
        (6, 1),
        (7, 4),
        (8, 3),
        (9, None),
    ]

    async def replay_run():
        with Cassette.from_report(report).replay() as replay:

            @replay.tool("root")
            async def forbidden(name):
                pytest.fail("Live root function executed")

            @replay.tool("independent")
            async def independent():
                pytest.fail("Live independent function executed")

            assert await asyncio.gather(forbidden("a"), forbidden("b")) == outputs[:2]
            assert await independent() == outputs[2]

    asyncio.run(replay_run())


def test_interleaved_unrelated_root_is_not_silently_consumed():
    report, outputs = interleaved_capture()

    async def replay_run():
        replay = Cassette.from_report(report).replay()

        @replay.tool("root")
        async def root(name):
            pytest.fail("Live body executed")

        assert await root("a") == outputs[0]
        with pytest.raises(ReplayMismatch, match="5 unused"):
            replay.assert_consumed()
        assert await root("b") == outputs[1]
        with pytest.raises(ReplayMismatch, match="1 unused"):
            replay.assert_consumed()

    asyncio.run(replay_run())


def test_nested_child_cannot_be_explicitly_replayed_after_outer():
    report, _ = interleaved_capture()

    async def replay_run():
        replay = Cassette.from_report(report).replay()

        @replay.tool("root")
        async def root(name):
            pytest.fail("Live body executed")

        @replay.tool("leaf")
        async def leaf(name):
            pytest.fail("Live body executed")

        await root("a")
        with pytest.raises(ReplayMismatch):
            await leaf("a")
        with pytest.raises(ReplayMismatch, match="previously diverged"):
            await root("b")

    asyncio.run(replay_run())


def forest_trace(parents, tools):
    base = Storm(clock=VirtualClock())

    @base.tool("base")
    def source(value):
        return {"value": value}

    source(0)
    data = base.report().to_dict()
    prototype = data["calls"][0]
    ordinals = {}
    calls = []
    for index, (parent, tool) in enumerate(zip(parents, tools, strict=True), 1):
        ordinals[tool] = ordinals.get(tool, 0) + 1
        call = copy.deepcopy(prototype)
        call.update(
            id=index,
            parent_id=parent,
            tool=tool,
            ordinal=ordinals[tool],
            key=f"#{ordinals[tool]}",
            arguments={"value": index},
            output={"value": index},
        )
        calls.append(call)
    data["calls"] = calls
    return data


@pytest.mark.parametrize("seed", range(50))
def test_arbitrary_interleaved_forests_only_require_roots(seed):
    rng = random.Random(seed)
    parents = [None]
    for index in range(2, 201):
        parents.append(rng.choice([None, *range(1, index)]))
    tools = [rng.choice(("a", "b", "c")) for _ in parents]
    data = forest_trace(parents, tools)
    with Cassette(data).replay() as replay:
        wrappers = {}
        for name in set(tools):

            def forbidden(value):
                pytest.fail("Live body executed")

            wrappers[name] = replay.tool(name)(forbidden)
        for index, parent in enumerate(parents, 1):
            if parent is None:
                assert wrappers[tools[index - 1]](index) == {"value": index}


@pytest.mark.parametrize("parent", [0, -1, True, False, 1.0, "1", 2, 3, 100, [], {}])
def test_parent_must_be_earlier_nonbool_integer(parent):
    data = forest_trace([None, 1], ["a", "b"])
    data["calls"][1]["parent_id"] = parent
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_first_call_cannot_have_parent():
    data = forest_trace([None], ["a"])
    data["calls"][0]["parent_id"] = 1
    with pytest.raises(ConfigurationError):
        Cassette(data)


@pytest.mark.parametrize("case", ["not-executed", "start-before-parent", "end-after-parent"])
def test_parent_execution_and_temporal_containment(case):
    data = forest_trace([None, 1], ["a", "b"])
    parent, child = data["calls"]
    if case == "not-executed":
        parent["executed"] = False
    elif case == "start-before-parent":
        parent["started"] = 1
    else:
        child["elapsed"] = 1
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_caught_nested_error_does_not_leak_through_successful_outer():
    storm = Storm(clock=VirtualClock())

    @storm.tool("inner")
    def inner():
        raise ValueError("hidden")

    @storm.tool("outer")
    def outer():
        try:
            inner()
        except ValueError:
            return {"recovered": True}

    outer()
    with Cassette.from_report(storm.report()).replay() as replay:

        @replay.tool("outer")
        def forbidden():
            pytest.fail("Live body executed")

        assert forbidden() == {"recovered": True}


def test_outer_error_still_consumes_descendants():
    storm = Storm(clock=VirtualClock())

    @storm.tool("inner")
    def inner():
        raise ValueError("hidden")

    @storm.tool("outer")
    def outer():
        return inner()

    with pytest.raises(ValueError):
        outer()
    with Cassette.from_report(storm.report()).replay() as replay:

        @replay.tool("outer")
        def forbidden():
            pytest.fail("Live body executed")

        with pytest.raises(RecordedToolError):
            forbidden()


def test_completed_inherited_context_starts_new_root():
    async def scenario():
        storm = Storm(clock=VirtualClock())
        gate = asyncio.Event()
        tasks = []

        @storm.tool("late")
        async def late():
            return "late"

        async def child_task():
            await gate.wait()
            return await late()

        @storm.tool("root")
        async def root():
            tasks.append(asyncio.create_task(child_task()))
            return "root"

        await root()
        gate.set()
        await tasks[0]
        report = storm.report()
        assert [c["parent_id"] for c in report.calls] == [None, None]
        Cassette.from_report(report)

    asyncio.run(scenario())


def test_concurrent_replay_cannot_duplicate_one_recorded_call():
    # Both calls start after the earlier expected record has been read. The
    # redactor deliberately yields the thread to make an ordinary data race
    # reproducible. No dynamic behavior occurs in the recording or live tools.
    storm = Storm(clock=VirtualClock())

    @storm.tool("echo")
    def echo(value):
        return value

    echo(1)
    barrier = Barrier(2)

    class YieldingRedactor(Redactor):
        def scrub(self, value):
            # A serialized implementation may hold its lock around scrub.
            with suppress(BrokenBarrierError):
                barrier.wait(timeout=0.1)
            return super().scrub(value)

    replay = Cassette.from_report(storm.report()).replay(redactor=YieldingRedactor())

    @replay.tool("echo")
    def forbidden(value):
        pytest.fail("Live body executed")

    def invoke():
        try:
            return forbidden(1)
        except ReplayMismatch:
            return "mismatch"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: invoke(), range(2)))
    assert results.count("mismatch") == 1
    with pytest.raises(ReplayMismatch):
        replay.assert_consumed()
