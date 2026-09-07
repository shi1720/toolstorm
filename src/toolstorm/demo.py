"""An executable ambiguity-of-writes lab, shared by CLI and browser.

These are deterministic recovery policies, not LLM agents. Service calls and
side effects run in memory; reported durations are virtual, not benchmarks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import __version__
from .clock import VirtualClock
from .contracts import Contract
from .engine import Storm
from .errors import (
    BudgetExceeded,
    ConfigurationError,
    RateLimited,
    ResponseLost,
    ToolTimeout,
    ToolUnavailable,
)
from .faults import Rule
from .serialization import fingerprint

SCENARIOS: dict[str, dict[str, Any]] = {
    "lost_ack": {
        "title": "Lost acknowledgement",
        "short": "Lost acknowledgement",
        "code": "INC-001",
        "category": "SIDE EFFECTS",
        "icon": "radio",
        "description": (
            "The first shipment commits, then its confirmation is lost. "
            "A retry may create a second shipment."
        ),
        "lesson": (
            "A successful retry can hide a duplicate shipment. Use the same idempotency "
            "key for the same logical operation."
        ),
        "rules": [
            {
                "name": "lost-receipt",
                "tool": "create_shipment",
                "kind": "response_lost",
                "calls": [1],
            }
        ],
    },
    "rate_limit": {
        "title": "Rate-limited inventory reads",
        "short": "Rate limit",
        "code": "INC-002",
        "category": "RECOVERY",
        "icon": "gauge",
        "description": (
            "Inventory rejects the first two reads with a retry-after hint. Can the "
            "policy recover within budget?"
        ),
        "lesson": (
            "Retries need a bound and a backoff. The resilient policy honors the "
            "supplied retry-after delay."
        ),
        "rules": [
            {
                "name": "inventory-busy",
                "tool": "check_inventory",
                "kind": "rate_limit",
                "calls": [1, 2],
                "delay": 0.6,
            }
        ],
    },
    "schema_drift": {
        "title": "Invalid inventory response",
        "short": "Malformed response",
        "code": "INC-003",
        "category": "VALIDATION",
        "icon": "braces",
        "description": (
            "Inventory returns a truthy string and a missing warehouse. Will the policy "
            "validate before acting?"
        ),
        "lesson": (
            "Syntactically valid JSON can still be unusable. Validate tool outputs "
            "before making dependent calls."
        ),
        "rules": [
            {
                "name": "bad-inventory",
                "tool": "check_inventory",
                "kind": "replace",
                "calls": [1],
                "replacement": {"available": "probably", "warehouse": None},
            }
        ],
    },
    "timeout": {
        "title": "Inventory read timeout",
        "short": "Read timeout",
        "code": "INC-004",
        "category": "RECOVERY",
        "icon": "clock",
        "description": (
            "The first inventory call times out before execution. Read retries can "
            "recover without duplicate writes."
        ),
        "lesson": (
            "Separate retryable read failures from ambiguous writes. A timeout alone is "
            "not proof that nothing happened."
        ),
        "rules": [
            {"name": "slow-inventory", "tool": "check_inventory", "kind": "timeout", "calls": [1]}
        ],
    },
    "latency": {
        "title": "Slow inventory response",
        "short": "Slow dependency",
        "code": "INC-005",
        "category": "LATENCY",
        "icon": "timer",
        "description": (
            "Inventory adds 1.4 seconds before returning. The task works, but does it "
            "meet the latency contract?"
        ),
        "lesson": (
            "Success is not the only contract. A tool can return correct data and still "
            "miss a time budget."
        ),
        "rules": [
            {
                "name": "inventory-lag",
                "tool": "check_inventory",
                "kind": "latency",
                "calls": [1],
                "delay": 1.4,
            }
        ],
    },
    "blackout": {
        "title": "Sustained inventory outage",
        "short": "Sustained outage",
        "code": "INC-006",
        "category": "TERMINATION",
        "icon": "unplug",
        "description": (
            "Every inventory read fails. Good behavior means stopping honestly without "
            "inventing a completed shipment."
        ),
        "lesson": (
            "No recovery policy can make an unavailable service succeed. Bounded, honest "
            "failure is the correct outcome."
        ),
        "rules": [{"name": "inventory-down", "tool": "check_inventory", "kind": "unavailable"}],
    },
}
POLICIES: dict[str, dict[str, str]] = {
    "optimistic": {
        "name": "No retries",
        "description": "One attempt per operation. No output validation.",
        "code": "No retries · no validation",
    },
    "retry": {
        "name": "Unchecked retries",
        "description": "Up to 3 attempts. No validation or idempotency.",
        "code": "3 attempts · fresh write each time",
    },
    "resilient": {
        "name": "Validated retries",
        "description": "Validate outputs, back off, and reuse write keys.",
        "code": "3 attempts · bounded, stable-key retries",
    },
}
TRANSIENT = (RateLimited, ToolTimeout, ResponseLost, ToolUnavailable)


def run_policy(
    policy: str,
    inventory: Callable[..., Any],
    ship: Callable[..., Any],
    clock: VirtualClock,
) -> dict[str, Any]:
    """The recovery code under test. ToolStorm itself never retries a call."""

    def attempt(tool: Callable[..., Any], **kwargs: Any) -> Any:
        attempts = 1 if policy == "optimistic" else 3
        for index in range(attempts):
            try:
                value = tool(**kwargs)
                if (
                    policy == "resilient"
                    and tool is inventory
                    and (
                        not isinstance(value, dict)
                        or type(value.get("available")) is not bool
                        or not isinstance(value.get("warehouse"), str)
                    )
                ):
                    raise ValueError("Inventory result violates the response contract")
                return value
            except Exception as exc:
                if isinstance(exc, BudgetExceeded):
                    raise
                retryable = isinstance(exc, TRANSIENT) or (
                    tool is inventory and isinstance(exc, ValueError)
                )
                if index == attempts - 1 or (policy == "resilient" and not retryable):
                    raise
                wait = 0.0
                if policy == "resilient":
                    wait = exc.retry_after if isinstance(exc, RateLimited) else 0.15 * 2**index
                clock.sleep(wait)
        raise AssertionError("unreachable")

    stock = attempt(inventory, sku="CLOUD-01")
    if not stock["available"]:
        return {"completed": False, "reason": "Out of stock"}
    receipt = attempt(
        ship,
        order_id="order-1729",
        warehouse=stock["warehouse"],
        idempotency_key="order-1729" if policy == "resilient" else None,
    )
    return {"completed": True, "receipt": receipt}


def run_demo(
    scenario: str = "lost_ack",
    policy: str = "resilient",
    seed: int = 42,
    probability: float = 1.0,
    max_calls: int = 8,
) -> dict[str, Any]:
    if scenario not in SCENARIOS or policy not in POLICIES:
        raise ConfigurationError("Unknown demo scenario or policy")
    if type(max_calls) is not int or not 1 <= max_calls <= 20:
        raise ConfigurationError("Demo call budget must be between 1 and 20")
    rules = [
        Rule.from_dict({**r, "probability": probability}) for r in SCENARIOS[scenario]["rules"]
    ]
    clock = VirtualClock()
    storm = Storm(rules, seed=seed, clock=clock, max_calls=max_calls)
    shipments: list[dict[str, Any]] = []
    receipts: dict[str, dict[str, Any]] = {}

    @storm.tool("check_inventory")
    def inventory(sku: str) -> dict[str, Any]:
        clock.sleep(0.08)
        return {"sku": sku, "available": True, "warehouse": "AMS-01"}

    @storm.tool("create_shipment")
    def ship(order_id: str, warehouse: str, idempotency_key: str | None = None) -> dict[str, Any]:
        clock.sleep(0.12)
        if not isinstance(warehouse, str) or not warehouse:
            raise ValueError("A valid warehouse is required")
        if idempotency_key and idempotency_key in receipts:
            return dict(receipts[idempotency_key])
        receipt = {
            "shipment_id": f"SHP-{len(shipments) + 1:04d}",
            "order_id": order_id,
            "warehouse": warehouse,
        }
        shipments.append(receipt)
        storm.effect("shipment", order_id)
        if idempotency_key:
            receipts[idempotency_key] = receipt
        return dict(receipt)

    try:
        outcome = run_policy(policy, inventory, ship, clock)
    except Exception as exc:
        outcome = {"completed": False, "reason": type(exc).__name__}
    report = storm.report()
    contract = Contract(report).require_triggered().no_duplicate_effects().at_most_calls(max_calls)
    if scenario == "rate_limit":
        violations = 0
        for index, call in enumerate(report.calls):
            if (
                call["error"]
                and call["error"].get("known")
                and call["error"]["type"] == "RateLimited"
            ):
                following = next(
                    (c for c in report.calls[index + 1 :] if c["tool"] == call["tool"]), None
                )
                if (
                    following is not None
                    and following["started"] + 0.000002
                    < call["started"] + call["elapsed"] + call["error"]["retry_after"]
                ):
                    violations += 1
        contract.check(
            "Retry-after respected",
            violations == 0,
            f"{violations} retry(s) occurred before the advertised delay",
        )
    if scenario == "blackout":
        # If probability misses and the service responds, success is valid too.
        handled = bool(outcome["completed"] or not shipments)
        contract.check("Honest outcome", handled, "A stopped task never claims to have shipped")
    else:
        contract.check(
            "Task completed",
            bool(outcome["completed"]),
            "Shipment confirmed" if outcome["completed"] else "No confirmed shipment",
        )
    contract.check("Latency budget", clock.now() <= 1.5, f"{clock.now():.2f}s / 1.50s virtual time")
    data = report.to_dict()
    result = {
        "scenario": scenario,
        "policy": policy,
        "seed": seed,
        "config": {
            "scenario": scenario,
            "seed": seed,
            "probability": probability,
            "max_calls": max_calls,
        },
        "outcome": outcome,
        "shipments": shipments,
        "report": data,
        "contract": contract.to_dict(),
        "stats": {
            "calls": len(report.calls),
            "effects": len(shipments),
            "faults": sum(v["triggered"] for v in report.coverage.values()),
            "elapsed": round(clock.now(), 6),
        },
        "digest": fingerprint(data),
    }
    return result


def run_comparison(
    scenario: str = "lost_ack",
    seed: int = 42,
    probability: float = 1.0,
    max_calls: int = 8,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "engine_version": __version__,
        "scenario": scenario,
        "config": {
            "scenario": scenario,
            "seed": seed,
            "probability": probability,
            "max_calls": max_calls,
        },
        "runs": [run_demo(scenario, policy, seed, probability, max_calls) for policy in POLICIES],
    }
