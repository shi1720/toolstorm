"""Strict offline boundary replay. No network fall-through or dynamic imports."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, cast

from .clock import duration
from .engine import Report
from .errors import (
    ConfigurationError,
    RateLimited,
    RecordedToolError,
    ReplayMismatch,
    ResponseLost,
    ToolTimeout,
    ToolUnavailable,
)
from .serialization import (
    MAX_DOCUMENT_BYTES,
    Redactor,
    canonical,
    json_value,
    load_json,
    require_keys,
)

F = TypeVar("F", bound=Callable[..., Any])
CALL_KEYS = {
    "id",
    "tool",
    "ordinal",
    "parent_id",
    "key",
    "started",
    "elapsed",
    "status",
    "fault",
    "kind",
    "executed",
    "injected",
    "arguments",
    "output",
    "error",
    "capture_error",
}
REPORT_KEYS = {
    "schema_version",
    "seed",
    "clock",
    "calls",
    "effects",
    "rules",
    "coverage",
    "budget_rejections",
    "capture",
}


def validate_report(data: Any) -> dict[str, Any]:
    """Validate a versioned trace before a reader trusts it."""
    require_keys(data, REPORT_KEYS)
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigurationError("Unsupported trace schema version; expected 1")
    if type(data["capture"]) is not bool or type(data["seed"]) is not int:
        raise ConfigurationError("Invalid trace metadata")
    if type(data["clock"]) is not str or type(data["budget_rejections"]) is not int:
        raise ConfigurationError("Invalid trace metadata")
    if data["budget_rejections"] < 0:
        raise ConfigurationError("Invalid rejected call count")
    if type(data["calls"]) is not list or len(data["calls"]) > 10_000:
        raise ConfigurationError("Invalid trace call list")
    ordinals: dict[str, int] = {}
    for index, call in enumerate(data["calls"], 1):
        require_keys(call, CALL_KEYS)
        if type(call["id"]) is not int or call["id"] != index:
            raise ConfigurationError("Trace calls must have contiguous invocation IDs")
        if not isinstance(call["tool"], str) or not call["tool"]:
            raise ConfigurationError("Invalid recorded tool name")
        if not isinstance(call["key"], str) or not call["key"]:
            raise ConfigurationError("Invalid recorded invocation key")
        ordinal = ordinals.get(call["tool"], 0) + 1
        if type(call["ordinal"]) is not int or call["ordinal"] != ordinal:
            raise ConfigurationError("Invalid per-tool invocation ordinal")
        ordinals[call["tool"]] = ordinal
        parent_id = call["parent_id"]
        if parent_id is not None:
            if type(parent_id) is not int or not 1 <= parent_id < index:
                raise ConfigurationError("Parent must be an earlier call")
            parent = data["calls"][parent_id - 1]
            if not parent["executed"]:
                raise ConfigurationError("Nested call requires an executing parent")
        duration(call["started"])
        duration(call["elapsed"])
        if parent_id is not None:
            if call["started"] < parent["started"]:
                raise ConfigurationError("Nested call precedes its parent")
            if (
                parent["status"] != "running"
                and call["started"] + call["elapsed"]
                > parent["started"] + parent["elapsed"] + 0.000002
            ):
                raise ConfigurationError("Nested call must finish before its parent")
        if call["status"] not in ("ok", "error", "cancelled", "running"):
            raise ConfigurationError("Invalid recorded call status")
        if any(
            type(call[field]) is not bool for field in ("executed", "injected", "capture_error")
        ):
            raise ConfigurationError("Invalid recorded call flags")
        if call["fault"] is not None and type(call["fault"]) is not str:
            raise ConfigurationError("Invalid recorded fault")
        if call["kind"] not in (
            None,
            "timeout",
            "rate_limit",
            "unavailable",
            "response_lost",
            "replace",
            "latency",
        ):
            raise ConfigurationError("Invalid recorded fault kind")
        if call["status"] == "ok" and call["error"] is not None:
            raise ConfigurationError("Successful call cannot contain an error")
        if call["status"] == "ok" and call["kind"] != "replace" and not call["executed"]:
            raise ConfigurationError("Successful non-replacement call requires execution")
        if call["status"] in ("error", "cancelled"):
            require_keys(call["error"], {"type", "known"}, {"retry_after"})
            if (
                not isinstance(call["error"]["type"], str)
                or not 1 <= len(call["error"]["type"]) <= 200
            ):
                raise ConfigurationError("Invalid recorded exception type")
            known = call["error"]["known"]
            if type(known) is not bool:
                raise ConfigurationError("Invalid known-error discriminator")
            if known and call["error"]["type"] not in {
                "RateLimited",
                "ToolTimeout",
                "ResponseLost",
                "ToolUnavailable",
            }:
                raise ConfigurationError("Unknown portable error type")
            is_rate_limit = known and call["error"]["type"] == "RateLimited"
            if is_rate_limit != ("retry_after" in call["error"]):
                raise ConfigurationError("Rate limit errors must carry retry metadata")
            if "retry_after" in call["error"]:
                duration(call["error"]["retry_after"])
        if data["capture"] and not isinstance(call["arguments"], dict):
            raise ConfigurationError("Recorded arguments must be an object")
    if type(data["effects"]) is not list or len(data["effects"]) > 10_000:
        raise ConfigurationError("Invalid effect list")
    identities: dict[int, tuple[str, str]] = {}
    visible_identities: dict[tuple[str, str], int] = {}
    for effect in data["effects"]:
        require_keys(effect, {"name", "key", "call_id", "at", "identity", "redacted"})
        if not all(isinstance(effect[k], str) and effect[k] for k in ("name", "key")):
            raise ConfigurationError("Invalid effect metadata")
        if type(effect["call_id"]) is not int or not 1 <= effect["call_id"] <= len(data["calls"]):
            raise ConfigurationError("Effect references an absent call")
        duration(effect["at"])
        if (
            type(effect["identity"]) is not int
            or effect["identity"] < 1
            or type(effect["redacted"]) is not bool
        ):
            raise ConfigurationError("Invalid effect identity")
        call = data["calls"][effect["call_id"] - 1]
        if not call["executed"]:
            raise ConfigurationError("An unexecuted tool cannot commit a side effect")
        if effect["at"] < call["started"] or (
            call["status"] != "running"
            and effect["at"] > call["started"] + call["elapsed"] + 0.000002
        ):
            raise ConfigurationError("Effect time must fall within its call")
        pair = (effect["name"], effect["key"])
        identity = effect["identity"]
        if identity not in identities and identity != len(identities) + 1:
            raise ConfigurationError("Effect identities must be contiguous in first-seen order")
        if identity in identities and identities[identity] != pair:
            raise ConfigurationError("Effect identity changed its label")
        identities[identity] = pair
        if not effect["redacted"]:
            if pair in visible_identities and visible_identities[pair] != identity:
                raise ConfigurationError("Duplicate effect labels cannot have different identities")
            visible_identities[pair] = identity
    if type(data["rules"]) is not list or len(data["rules"]) > 100:
        raise ConfigurationError("Invalid rule list")
    from .faults import Rule

    rules = [Rule.from_dict(r) for r in data["rules"]]
    names = {r.name for r in rules}
    if (
        len(names) != len(rules)
        or type(data["coverage"]) is not dict
        or set(data["coverage"]) != names
    ):
        raise ConfigurationError("Rule coverage must match unique rule names")
    for coverage in data["coverage"].values():
        require_keys(coverage, {"eligible", "selected", "triggered"})
        if (
            any(type(v) is not int or v < 0 for v in coverage.values())
            or not coverage["triggered"] <= coverage["selected"] <= coverage["eligible"]
        ):
            raise ConfigurationError("Invalid rule coverage counts")
    indexed_rules = {rule.name: rule for rule in rules}
    expected_coverage = {r.name: {"eligible": 0, "selected": 0, "triggered": 0} for r in rules}
    for call in data["calls"]:
        for rule in rules:
            if rule.eligible(call["tool"], call["ordinal"]):
                expected_coverage[rule.name]["eligible"] += 1
        if call["fault"] is None:
            if call["kind"] is not None or call["injected"]:
                raise ConfigurationError("A fault kind needs a rule reference")
            continue
        if call["fault"] not in indexed_rules:
            raise ConfigurationError("Call references an unknown fault rule")
        rule = indexed_rules[call["fault"]]
        if rule.probability == 0:
            raise ConfigurationError("A probability-zero rule cannot be selected")
        if call["kind"] != rule.kind or not rule.eligible(call["tool"], call["ordinal"]):
            raise ConfigurationError("Call fault does not match its rule")
        expected_coverage[rule.name]["selected"] += 1
        expected_coverage[rule.name]["triggered"] += int(call["injected"])
        if rule.limit and expected_coverage[rule.name]["selected"] > rule.limit:
            raise ConfigurationError("Fault exceeds its trigger limit")
        if rule.kind in ("timeout", "rate_limit", "unavailable", "replace") and call["executed"]:
            raise ConfigurationError("Pre-call faults cannot execute the underlying tool")
        error_types = {
            "timeout": "ToolTimeout",
            "rate_limit": "RateLimited",
            "unavailable": "ToolUnavailable",
        }
        if rule.kind in error_types and call["status"] != "running":
            expected_error: dict[str, Any] = {"type": error_types[rule.kind], "known": True}
            if rule.kind == "rate_limit":
                expected_error["retry_after"] = rule.delay
            if call["status"] != "error" or call["error"] != expected_error:
                raise ConfigurationError("Pre-call failure must carry its declared error")
        if rule.kind == "replace" and call["status"] not in ("running", "ok"):
            raise ConfigurationError("Replacement must return its payload successfully")
        if (
            rule.kind == "replace"
            and call["status"] == "ok"
            and data["capture"]
            and not call["capture_error"]
            and canonical(call["output"]) != canonical(rule.replacement)
        ):
            raise ConfigurationError("Captured replacement disagrees with its rule payload")
        if rule.kind == "response_lost":
            if not call["executed"]:
                raise ConfigurationError("A lost acknowledgement requires execution")
            if call["injected"] and (
                call["status"] != "error"
                or call["error"] != {"type": "ResponseLost", "known": True}
            ):
                raise ConfigurationError(
                    "A triggered lost acknowledgement must record ResponseLost"
                )
        elif not call["injected"] and call["status"] != "running":
            raise ConfigurationError("A selected pre-call rule must record an injection")
    if data["coverage"] != expected_coverage:
        raise ConfigurationError("Coverage counts disagree with recorded calls")
    return cast(dict[str, Any], json_value(data))


class Cassette:
    """A detached, versioned trace. Loading never runs code from the file."""

    def __init__(self, data: dict[str, Any]) -> None:
        serialized = canonical(data)
        if len(serialized.encode()) > MAX_DOCUMENT_BYTES:
            raise ConfigurationError("Cassette exceeds 8 MB limit")
        self._data = validate_report(load_json(serialized))

    @classmethod
    def from_report(cls, report: Report) -> Cassette:
        return cls(report.to_dict())

    @classmethod
    def loads(cls, text: str) -> Cassette:
        return cls(load_json(text))

    @classmethod
    def load(cls, path: str | Path) -> Cassette:
        # Bounded read also protects against files which grow after stat().
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_DOCUMENT_BYTES + 1)
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ConfigurationError("Cassette exceeds 8 MB limit")
        try:
            return cls.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ConfigurationError("Cassette must be UTF-8 JSON") from exc

    def to_dict(self) -> dict[str, Any]:
        return cast(dict[str, Any], json_value(self._data))

    def dumps(self) -> str:
        return canonical(self._data) + "\n"

    def save(self, path: str | Path) -> None:
        from .io import write_text

        write_text(Path(path), self.dumps())

    def replay(self, *, redactor: Redactor | None = None) -> Replay:
        return Replay(self, redactor=redactor)


class Replay:
    """Consume recorded calls in invocation order; live tools are never called.

    Matching uses redacted, signature-bound arguments, so scrubbed secrets are
    intentionally indistinguishable. Supply the same Redactor used for capture.
    Replay covers only decorated boundaries, not other code or external I/O.
    Effects are evidence from capture and are not executed during replay.
    """

    def __init__(self, cassette: Cassette, *, redactor: Redactor | None = None) -> None:
        self._data = cassette.to_dict()
        if not self._data["capture"] or self._data["budget_rejections"]:
            raise ConfigurationError("Replay needs captured payloads and no refused calls")
        if any(
            c["status"] not in ("ok", "error") or c["capture_error"] for c in self._data["calls"]
        ):
            raise ConfigurationError("Replay requires complete, JSON-capturable calls")
        self._lock = RLock()
        self._position = 0
        self._consumed: set[int] = set()
        roots: dict[int, int] = {}
        self._groups: dict[int, list[int]] = {}
        for index, call in enumerate(self._data["calls"]):
            root = roots[call["parent_id"]] if call["parent_id"] is not None else call["id"]
            roots[call["id"]] = root
            self._groups.setdefault(root, []).append(index)
        self.redactor = redactor or Redactor()
        self._failed = False

    def __enter__(self) -> Replay:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.assert_consumed()

    def assert_consumed(self) -> None:
        with self._lock:
            if self._failed:
                raise ReplayMismatch("Replay previously diverged")
            remaining = len(self._data["calls"]) - len(self._consumed)
            if remaining:
                raise ReplayMismatch(f"Replay ended with {remaining} unused call(s)")

    def _consume(self, name: str, arguments: Any) -> Any:
        with self._lock:
            if self._failed:
                raise ReplayMismatch("Replay previously diverged")
            if self._position >= len(self._data["calls"]):
                self._failed = True
                raise ReplayMismatch("Replay received an extra call")
            expected = self._data["calls"][self._position]
            try:
                normalized = canonical(self.redactor.scrub(arguments))
            except ConfigurationError:
                self._failed = True
                raise ReplayMismatch("Replay arguments could not be normalized") from None
            if expected["tool"] != name or canonical(expected["arguments"]) != normalized:
                self._failed = True
                # Never echo actual args or other potentially sensitive input.
                raise ReplayMismatch(f"Tool or arguments differ at call {self._position + 1}")
            # Stubbing an outer boundary also stubs its internal call subtree. Parent
            # links allow unrelated concurrent roots to remain pending, even when interleaved.
            self._consumed.update(self._groups[expected["id"]])
            while self._position in self._consumed:
                self._position += 1
        if expected["status"] == "error":
            error = expected["error"]
            kind = error["type"]
            if not error["known"]:
                raise RecordedToolError(kind)
            if kind == "RateLimited":
                raise RateLimited(error.get("retry_after", 0.0))
            factories = {
                "ToolTimeout": ToolTimeout,
                "ResponseLost": ResponseLost,
                "ToolUnavailable": ToolUnavailable,
            }
            if kind in factories:
                raise factories[kind]("Replayed tool failure")
            raise RecordedToolError(kind)
        return json_value(expected["output"])

    def tool(self, name: str | None = None) -> Callable[[F], F]:
        def decorate(func: F) -> F:
            tool_name = name or getattr(func, "__name__", "")
            if not isinstance(tool_name, str) or not tool_name:
                raise ConfigurationError("Replay tool needs a name")
            if (
                inspect.isgeneratorfunction(func)
                or inspect.isasyncgenfunction(func)
                or not (inspect.isfunction(func) or inspect.ismethod(func))
            ):
                raise ConfigurationError("Replay supports sync/async functions only")
            signature = inspect.signature(func)

            def invoke(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
                try:
                    bound = signature.bind(*args, **kwargs)
                    bound.apply_defaults()
                except TypeError:
                    with self._lock:
                        self._failed = True
                    raise ReplayMismatch(
                        "Replay call does not bind to the tool signature"
                    ) from None
                return self._consume(tool_name, dict(bound.arguments))

            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    return invoke(args, kwargs)

                return cast(F, async_wrapper)

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return invoke(args, kwargs)

            return cast(F, wrapper)

        return decorate
