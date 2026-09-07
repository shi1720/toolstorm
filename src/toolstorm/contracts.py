"""Behavioral assertions with evidence; no synthetic resilience scores."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .engine import Report
from .errors import ConfigurationError


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Contract:
    """Chain explicit checks, inspect results, then assert_valid() in CI."""

    def __init__(self, report: Report) -> None:
        self.report = report
        self.checks: list[Check] = []

    def require_triggered(self, *names: str) -> Contract:
        wanted = list(names) if names else list(self.report.coverage)
        for name in wanted:
            count = self.report.coverage.get(name, {}).get("triggered", 0)
            self.checks.append(
                Check(f"Fault exercised: {name}", count > 0, f"Triggered {count} time(s)")
            )
        return self

    def at_most_calls(self, count: int, *, tool: str | None = None) -> Contract:
        if type(count) is not int or count < 0:
            raise ConfigurationError("Call limit must be a nonnegative integer")
        actual = sum(1 for c in self.report.calls if tool is None or c["tool"] == tool)
        # Global budgets include refused attempts; per-tool rejected names are not recorded.
        if tool is None:
            actual += self.report.budget_rejections
        self.checks.append(Check("Call budget", actual <= count, f"{actual} / {count} calls"))
        return self

    def at_most_effects(self, name: str, count: int, *, key: str | None = None) -> Contract:
        if type(count) is not int or count < 0:
            raise ConfigurationError("Effect limit must be a nonnegative integer")
        if any(e.get("redacted", False) for e in self.report.effects):
            self.checks.append(
                Check(
                    f"Effect budget: {name}",
                    False,
                    "Cannot filter redacted effect identities; use nonsecret identifiers",
                )
            )
            return self
        actual = sum(
            1 for e in self.report.effects if e["name"] == name and (key is None or e["key"] == key)
        )
        self.checks.append(
            Check(
                f"Effect budget: {name}", actual <= count, f"{actual} / {count} committed effects"
            )
        )
        return self

    def no_duplicate_effects(self) -> Contract:
        counts = Counter(e["identity"] for e in self.report.effects)
        duplicates = sum(v - 1 for v in counts.values())
        self.checks.append(
            Check(
                "No duplicate side effects",
                duplicates == 0,
                f"{duplicates} duplicate effect(s) across {sum(counts.values())} commits",
            )
        )
        return self

    def check(self, name: str, passed: bool, detail: str) -> Contract:
        if type(passed) is not bool:
            raise ConfigurationError("Contract condition must be a boolean")
        self.checks.append(Check(name, passed, detail))
        return self

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def assert_valid(self) -> None:
        if not self.checks:
            raise AssertionError("An empty contract cannot establish correctness")
        failures = [f"{c.name}: {c.detail}" for c in self.checks if not c.passed]
        if failures:
            raise AssertionError("ToolStorm contract failed\n" + "\n".join(failures))

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}
