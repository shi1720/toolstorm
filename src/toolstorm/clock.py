"""Injectable clocks. Virtual time describes requested delays, not CPU time."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Protocol

from .errors import ConfigurationError


def duration(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError("Duration must be a finite nonnegative number")
    try:
        converted = float(value)
    except (ValueError, OverflowError) as exc:
        raise ConfigurationError("Duration must be a finite nonnegative number") from exc
    if not math.isfinite(converted) or converted < 0:
        raise ConfigurationError("Duration must be a finite nonnegative number")
    return converted


class Clock(Protocol):
    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...
    async def asleep(self, seconds: float) -> None: ...


class RealClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(duration(seconds))

    async def asleep(self, seconds: float) -> None:
        await asyncio.sleep(duration(seconds))


class VirtualClock:
    """A no-wait clock for sequential tests, not a concurrent event simulator."""

    def __init__(self) -> None:
        self._time = 0.0

    def now(self) -> float:
        return self._time

    def sleep(self, seconds: float) -> None:
        self._time += duration(seconds)

    async def asleep(self, seconds: float) -> None:
        self.sleep(seconds)
        await asyncio.sleep(0)
