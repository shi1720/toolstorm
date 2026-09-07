"""Record tools, then replay a workflow without calling the live functions."""

from toolstorm import Cassette, Storm, VirtualClock


def main() -> None:
    storm = Storm(clock=VirtualClock())

    @storm.tool("lookup")
    def lookup(sku: str, region: str = "eu") -> dict[str, object]:
        return {"sku": sku, "region": region, "available": True}

    original = lookup("CLOUD-01")
    cassette = Cassette.from_report(storm.report())
    # cassette.save("lookup.json")  # owner-readable atomic file, if desired

    with cassette.replay() as replay:  # fails if any recorded calls remain unused

        @replay.tool("lookup")
        def offline_lookup(sku: str, region: str = "eu") -> dict[str, object]:
            raise AssertionError("Live code must never execute during replay")

        assert offline_lookup(region="eu", sku="CLOUD-01") == original
    print("Offline replay consumed every recorded boundary without live execution.")


if __name__ == "__main__":
    main()
