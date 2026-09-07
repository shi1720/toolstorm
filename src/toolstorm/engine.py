"""A framework-neutral boundary engine. The application owns recovery policy."""

from __future__ import annotations

import contextvars
import functools
import inspect
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, TypeVar, cast

from .clock import Clock, RealClock
from .errors import (
    BudgetExceeded,
    ConfigurationError,
    RateLimited,
    ResponseLost,
    ToolTimeout,
    ToolUnavailable,
)
from .faults import Rule
from .serialization import Redactor, fingerprint, json_value

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class Call:
    id: int
    tool: str
    ordinal: int
    key: str
    started: float
    parent_id: int | None = None
    elapsed: float = 0.0
    status: str = "running"
    fault: str | None = None
    kind: str | None = None
    executed: bool = False
    injected: bool = False
    arguments: Any = None
    output: Any = None
    error: dict[str, Any] | None = None
    capture_error: bool = False


@dataclass
class Coverage:
    eligible: int = 0
    selected: int = 0
    triggered: int = 0


@dataclass
class Effect:
    name: str
    key: str
    call_id: int
    at: float
    identity: int
    redacted: bool


@dataclass
class Report:
    seed: int
    clock: str
    calls: list[dict[str, Any]]
    effects: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    coverage: dict[str, dict[str, int]]
    budget_rejections: int
    capture: bool
    schema_version: int = field(default=1, init=False)

    def to_dict(self) -> dict[str, Any]:
        return json_value(asdict(self))  # type: ignore[no-any-return]

    @property
    def digest(self) -> str:
        """Digest of the exported report. Wall-clock reports include variable timings."""
        return fingerprint(self.to_dict())


class Storm:
    """Wrap tools with deterministic faults and a bounded, redacted trace.

    Each instance is one test run. Rules are copied at construction. Decisions
    are deterministic for a fixed seed and per-tool invocation order. Independent
    tools do not perturb one another. Explicit invocation keys stabilize random
    draws across same-tool scheduling, but ordinal filters/limits remain ordered.
    """

    def __init__(
        self,
        rules: Sequence[Rule] = (),
        *,
        seed: int = 0,
        clock: Clock | None = None,
        max_calls: int = 1000,
        capture: bool = True,
        redactor: Redactor | None = None,
    ) -> None:
        if type(seed) is not int or not -(2**53 - 1) <= seed <= 2**53 - 1:
            raise ConfigurationError("Seed must be an integer in the JavaScript-safe range")
        if type(max_calls) is not int or not 1 <= max_calls <= 10_000:
            raise ConfigurationError("max_calls must be an integer between 1 and 10000")
        if type(capture) is not bool:
            raise ConfigurationError("capture must be a boolean")
        self.rules = tuple(Rule.from_dict(r.to_dict()) for r in rules)
        if len(self.rules) > 100 or len({r.name for r in self.rules}) != len(self.rules):
            raise ConfigurationError("Use at most 100 uniquely named rules")
        self.seed = seed
        self.clock: Clock = clock or RealClock()
        self.max_calls = max_calls
        self.capture = capture
        self.redactor = redactor or Redactor()
        self._start = self.clock.now()
        self._calls: list[Call] = []
        self._effects: list[Effect] = []
        self._effect_ids: dict[tuple[str, str], int] = {}
        self._coverage = {r.name: Coverage() for r in self.rules}
        self._ordinals: dict[str, int] = {}
        self._keys: set[tuple[str, str]] = set()
        self._budget_rejections = 0
        self._lock = threading.RLock()
        self._active: contextvars.ContextVar[Call | None] = contextvars.ContextVar(
            "call", default=None
        )
        self._key: contextvars.ContextVar[str | None] = contextvars.ContextVar("key", default=None)

    @contextmanager
    def invocation(self, key: str) -> Iterator[None]:
        """Give this logical invocation a stable key (unique per tool per run)."""
        if not isinstance(key, str) or not key or len(key) > 200:
            raise ConfigurationError("Invocation key must be 1–200 characters")
        token = self._key.set(key)
        try:
            yield
        finally:
            self._key.reset(token)

    def effect(self, name: str, key: str) -> None:
        """Record an actual fixture side effect, at the point it commits.

        This is explicit instrumentation, not automatic detection. Repeated keys
        identify repeated logical effects even if the service's row IDs differ.
        """
        call = self._active.get()
        if call is None:
            raise ConfigurationError("effect() must be called inside an executing wrapped tool")
        if not all(isinstance(v, str) and 0 < len(v) <= 200 for v in (name, key)):
            raise ConfigurationError("Effect name and key must be 1–200 characters")
        with self._lock:
            if call.status != "running":
                raise ConfigurationError("Cannot record an effect after its wrapped call completed")
            if len(self._effects) >= 10_000:
                raise BudgetExceeded("Effect trace limit reached")
            safe_name, safe_key = self.redactor.scrub(name), self.redactor.scrub(key)
            identity = self._effect_ids.setdefault((name, key), len(self._effect_ids) + 1)
            self._effects.append(
                Effect(
                    safe_name,
                    safe_key,
                    call.id,
                    round(self.clock.now() - self._start, 6),
                    identity,
                    safe_name != name or safe_key != key,
                )
            )

    def _begin(self, name: str, arguments: Any) -> tuple[Call, Rule | None]:
        with self._lock:
            if len(self._calls) >= self.max_calls:
                self._budget_rejections += 1
                raise BudgetExceeded(f"Tool call budget of {self.max_calls} exhausted")
            ordinal = self._ordinals.get(name, 0) + 1
            key = self._key.get() or f"#{ordinal}"
            if (name, key) in self._keys:
                raise ConfigurationError("Duplicate invocation key for this tool")
            captured = self.redactor.scrub(arguments) if self.capture else None
            self._keys.add((name, key))
            self._ordinals[name] = ordinal
            selected = None
            for rule in self.rules:
                if rule.eligible(name, ordinal):
                    coverage = self._coverage[rule.name]
                    coverage.eligible += 1
                    if (
                        selected is None
                        and (rule.limit is None or coverage.selected < rule.limit)
                        and rule.draw(self.seed, name, key)
                    ):
                        selected = rule
                        coverage.selected += 1
            parent = self._active.get()
            call = Call(
                id=len(self._calls) + 1,
                parent_id=parent.id if parent is not None and parent.status == "running" else None,
                tool=name,
                ordinal=ordinal,
                key=self.redactor.scrub(key),
                started=round(self.clock.now() - self._start, 6),
                fault=selected.name if selected else None,
                kind=selected.kind if selected else None,
                arguments=captured,
            )
            self._calls.append(call)
            return call, selected

    def _mark_injected(self, call: Call, rule: Rule) -> None:
        with self._lock:
            if not call.injected:
                call.injected = True
                self._coverage[rule.name].triggered += 1

    def _before(self, call: Call, rule: Rule | None) -> None:
        if rule is None:
            return
        if rule.kind != "response_lost":
            self._mark_injected(call, rule)
        if rule.kind == "timeout":
            raise ToolTimeout("Injected timeout before execution")
        if rule.kind == "rate_limit":
            raise RateLimited(rule.delay)
        if rule.kind == "unavailable":
            raise ToolUnavailable("Injected service outage before execution")

    def _success(self, call: Call, result: Any, rule: Rule | None) -> Any:
        if rule and rule.kind == "response_lost":
            self._mark_injected(call, rule)
            raise ResponseLost("Tool completed; acknowledgement was lost")
        if self.capture:
            try:
                call.output = self.redactor.scrub(result)
            except ConfigurationError:
                call.capture_error = True
                # Observability must not turn a successful write into a failed call.
                # This trace will be refused by Replay.
        call.status = "ok"
        return result

    @staticmethod
    def _failure(call: Call, exc: BaseException) -> None:
        # No exception messages, traceback locals, or repr values are captured.
        call.status = "error" if isinstance(exc, Exception) else "cancelled"
        known = type(exc) in (RateLimited, ToolTimeout, ResponseLost, ToolUnavailable)
        call.error = {"type": type(exc).__name__, "known": known}
        if type(exc) is RateLimited:
            call.error["retry_after"] = exc.retry_after

    def tool(self, name: str | None = None) -> Callable[[F], F]:
        """Decorate a sync or async JSON-oriented tool without framework coupling."""

        def decorate(func: F) -> F:
            tool_name = name or getattr(func, "__name__", "")
            if not isinstance(tool_name, str) or not tool_name or len(tool_name) > 200:
                raise ConfigurationError("Tool name must be 1–200 characters")
            if (
                inspect.isgeneratorfunction(func)
                or inspect.isasyncgenfunction(func)
                or not (inspect.isfunction(func) or inspect.ismethod(func))
            ):
                raise ConfigurationError("Wrap a sync/async function; generators are unsupported")
            signature = inspect.signature(func)

            def bind(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                return dict(bound.arguments)

            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    call, rule = self._begin(tool_name, bind(args, kwargs))
                    token = self._active.set(call)
                    try:
                        self._before(call, rule)
                        if rule and rule.kind == "latency":
                            await self.clock.asleep(rule.delay)
                        if rule and rule.kind == "replace":
                            result = json_value(rule.replacement)
                        else:
                            call.executed = True
                            result = await func(*args, **kwargs)
                        return self._success(call, result, rule)
                    except BaseException as exc:
                        self._failure(call, exc)
                        raise
                    finally:
                        call.elapsed = round(self.clock.now() - self._start - call.started, 6)
                        self._active.reset(token)

                return cast(F, async_wrapper)

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                call, rule = self._begin(tool_name, bind(args, kwargs))
                token = self._active.set(call)
                try:
                    self._before(call, rule)
                    if rule and rule.kind == "latency":
                        self.clock.sleep(rule.delay)
                    if rule and rule.kind == "replace":
                        result = json_value(rule.replacement)
                    else:
                        call.executed = True
                        result = func(*args, **kwargs)
                    return self._success(call, result, rule)
                except BaseException as exc:
                    self._failure(call, exc)
                    raise
                finally:
                    call.elapsed = round(self.clock.now() - self._start - call.started, 6)
                    self._active.reset(token)

            return cast(F, sync_wrapper)

        return decorate

    def report(self) -> Report:
        """Return a detached snapshot; inspect after joining concurrent tasks."""
        with self._lock:
            rules = []
            for rule in self.rules:
                data = rule.to_dict()
                # Replacement payloads can contain sensitive fixture data too.
                data["replacement"] = self.redactor.scrub(data["replacement"])
                rules.append(data)
            return Report(
                seed=self.seed,
                clock=type(self.clock).__name__,
                calls=[asdict(c) for c in self._calls],
                effects=[asdict(e) for e in self._effects],
                rules=rules,
                coverage={k: asdict(v) for k, v in self._coverage.items()},
                budget_rejections=self._budget_rejections,
                capture=self.capture,
            )
