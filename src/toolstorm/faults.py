"""Declarative fault rules with stable, independently hashed probability draws."""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

from .clock import duration
from .errors import ConfigurationError
from .serialization import canonical, json_value, require_keys

FaultKind = Literal["timeout", "rate_limit", "unavailable", "response_lost", "replace", "latency"]
KINDS = frozenset({"timeout", "rate_limit", "unavailable", "response_lost", "replace", "latency"})


@dataclass(frozen=True)
class Rule:
    """First matching rule wins; calls are 1-based per tool, in invocation order.

    replace substitutes a response WITHOUT calling the live function.
    response_lost calls it ONCE, then discards its successful acknowledgement.
    latency delays then calls it once. All other faults skip execution.
    """

    name: str
    tool: str
    kind: FaultKind
    calls: tuple[int, ...] = ()
    probability: float = 1.0
    limit: int | None = None
    delay: float = 0.0
    replacement: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name or len(self.name) > 100:
            raise ConfigurationError("Rule name must be 1–100 characters")
        if not isinstance(self.tool, str) or not self.tool or len(self.tool) > 200:
            raise ConfigurationError("Rule tool pattern must be 1–200 characters")
        if not isinstance(self.kind, str) or self.kind not in KINDS:
            raise ConfigurationError("Unknown fault kind")
        if not isinstance(self.calls, (tuple, list)) or any(
            type(c) is not int or c < 1 for c in self.calls
        ):
            raise ConfigurationError("Rule calls must be positive integer ordinals")
        if len(set(self.calls)) != len(self.calls):
            raise ConfigurationError("Rule calls cannot contain duplicates")
        object.__setattr__(self, "calls", tuple(sorted(self.calls)))
        object.__setattr__(self, "probability", duration(self.probability))
        object.__setattr__(self, "delay", duration(self.delay))
        if self.probability > 1:
            raise ConfigurationError("Rule probability must be between 0 and 1")
        if self.limit is not None and (type(self.limit) is not int or self.limit < 1):
            raise ConfigurationError("Rule limit must be a positive integer or null")
        object.__setattr__(self, "replacement", json_value(self.replacement))

    def eligible(self, tool: str, ordinal: int) -> bool:
        return fnmatch.fnmatchcase(tool, self.tool) and (not self.calls or ordinal in self.calls)

    def draw(self, seed: int, tool: str, key: str) -> bool:
        value = canonical([seed, self.name, tool, key]).encode()
        numerator = int.from_bytes(hashlib.sha256(value).digest()[:8], "big")
        return numerator < self.probability * (1 << 64)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tool": self.tool,
            "kind": self.kind,
            "calls": list(self.calls),
            "probability": self.probability,
            "limit": self.limit,
            "delay": self.delay,
            "replacement": json_value(self.replacement),
        }

    @classmethod
    def from_dict(cls, value: Any) -> Rule:
        require_keys(
            value,
            {"name", "tool", "kind"},
            {"calls", "probability", "limit", "delay", "replacement"},
        )
        try:
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("Invalid fault rule") from exc
