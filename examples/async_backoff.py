"""An async tool and application-owned, bounded retry-after handling."""

import asyncio

from toolstorm import Contract, RateLimited, Rule, Storm, VirtualClock


async def main() -> None:
    clock = VirtualClock()
    storm = Storm([Rule("busy", "search", "rate_limit", calls=(1, 2), delay=0.25)], clock=clock)

    @storm.tool("search")
    async def search(query: str) -> dict[str, str]:
        return {"answer": f"Result for {query}"}

    for _ in range(3):
        try:
            result = await search("resilience")
            break
        except RateLimited as exc:
            await clock.asleep(exc.retry_after)
    else:
        raise AssertionError("Retry budget exhausted")

    assert result["answer"] == "Result for resilience"
    assert clock.now() == 0.5
    Contract(storm.report()).require_triggered().at_most_calls(3).assert_valid()
    print("Async recovery passed; 0.5s of requested backoff, no wall-clock delay.")


if __name__ == "__main__":
    asyncio.run(main())
