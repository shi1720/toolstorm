"""A lost response after a successful write. Run: python examples/ambiguous_write.py"""

from toolstorm import Contract, ResponseLost, Rule, Storm, VirtualClock


def exercise(use_idempotency: bool) -> Contract:
    storm = Storm([Rule("lost-ack", "ship", "response_lost", calls=(1,))], clock=VirtualClock())
    ledger: list[str] = []
    completed: dict[str, dict[str, str]] = {}

    @storm.tool("ship")
    def ship(order: str, idempotency_key: str | None = None) -> dict[str, str]:
        if idempotency_key and idempotency_key in completed:
            return completed[idempotency_key]
        ledger.append(order)
        storm.effect("shipment", order)  # Instrument the commit, not the attempt.
        receipt = {"id": f"shipment-{len(ledger)}"}
        if idempotency_key:
            completed[idempotency_key] = receipt
        return receipt

    key = "order-1729" if use_idempotency else None
    try:
        ship("order-1729", key)
    except ResponseLost:
        ship("order-1729", key)

    return Contract(storm.report()).require_triggered().no_duplicate_effects().at_most_calls(2)


if __name__ == "__main__":
    broken = exercise(use_idempotency=False)
    assert not broken.passed, "Negative control must detect duplicate shipments"
    fixed = exercise(use_idempotency=True)
    fixed.assert_valid()
    print("Broken policy: duplicate detected. Idempotent policy: contract passed.")
