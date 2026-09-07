"""Local, machine-readable demo and cassette inspection. No server required."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .contracts import Contract
from .demo import POLICIES, SCENARIOS, run_comparison, run_demo
from .engine import Report
from .errors import ToolstormError
from .io import write_text
from .replay import Cassette
from .serialization import load_json


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="toolstorm", description="Break tools. Verify recovery.")
    root.add_argument("--version", action="version", version=f"toolstorm {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Run the in-memory shipping lab")
    demo.add_argument("--scenario", choices=SCENARIOS, default="lost_ack")
    demo.add_argument("--policy", choices=[*POLICIES, "all"], default="resilient")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--probability", type=float, default=1.0)
    demo.add_argument("--max-calls", type=int, default=8)
    demo.add_argument("--json", action="store_true", help="Print the complete JSON result")
    demo.add_argument("--output", type=Path, help="Save the complete result as JSON")
    demo.add_argument("--cassette", type=Path, help="Save a single policy trace for replay")
    demo.add_argument(
        "--fail-on-contract", action="store_true", help="Exit 1 if any contract fails"
    )
    inspect = commands.add_parser("inspect", help="Validate and summarize a trace")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--json", action="store_true")
    check = commands.add_parser("check", help="Validate trace contracts; exit 1 on a failed check")
    check.add_argument("path", type=Path)
    check.add_argument("--max-calls", type=int, default=100)
    check.add_argument("--json", action="store_true")
    commands.add_parser("scenarios", help="List bundled failure scenarios")
    return root


def _read_cassettes(path: Path) -> list[Cassette]:
    # Accept the browser's comparison export as well as standalone cassettes.
    with path.open("rb") as handle:
        raw = handle.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError("File exceeds 8 MB limit")
    data = load_json(raw.decode("utf-8"))
    if isinstance(data, dict) and "runs" in data:
        if type(data["runs"]) is not list or not 1 <= len(data["runs"]) <= 100:
            raise ValueError("Comparison needs 1–100 run records")
        if any(type(run) is not dict or "report" not in run for run in data["runs"]):
            raise ValueError("Each comparison run needs a report")
        return [Cassette(run["report"]) for run in data["runs"]]
    if isinstance(data, dict) and "report" in data:
        data = data["report"]
    return [Cassette(data)]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "scenarios":
            for name, details in SCENARIOS.items():
                print(f"{name:15} {details['title']}")
            return 0
        if args.command == "demo":
            config = {
                "scenario": args.scenario,
                "seed": args.seed,
                "probability": args.probability,
                "max_calls": args.max_calls,
            }
            result = (
                run_comparison(**config)
                if args.policy == "all"
                else run_demo(policy=args.policy, **config)
            )
            runs = result["runs"] if args.policy == "all" else [result]
            if args.cassette:
                if args.policy == "all":
                    raise ValueError("--cassette requires a single --policy")
                Cassette(result["report"]).save(args.cassette)
            serialized = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
            if args.output:
                write_text(args.output, serialized)
            if args.json:
                print(serialized, end="")
            else:
                title = SCENARIOS[args.scenario]["title"]
                print(f"ToolStorm · {title} · seed {args.seed}")
                for run in runs:
                    verdict = "PASS" if run["contract"]["passed"] else "FAIL"
                    stats = run["stats"]
                    print(
                        f"{verdict:4}  {POLICIES[run['policy']]['name']:24} "
                        f"{stats['calls']} calls · {stats['effects']} shipments · "
                        f"{stats['elapsed']:.2f}s virtual"
                    )
                    for check in run["contract"]["checks"]:
                        print(
                            f"  {'✓' if check['passed'] else '✗'} "
                            f"{check['name']}: {check['detail']}"
                        )
            return int(args.fail_on_contract and any(not r["contract"]["passed"] for r in runs))
        cassettes = _read_cassettes(args.path)
        summaries = []
        all_passed = True
        for cassette in cassettes:
            data = cassette.to_dict()
            if args.command == "inspect":
                summary: dict[str, Any] = {
                    "schema_version": data["schema_version"],
                    "calls": len(data["calls"]),
                    "effects": len(data["effects"]),
                    "coverage": data["coverage"],
                    "capture": data["capture"],
                }
                summaries.append(summary)
                if not args.json:
                    print(
                        f"Valid trace v{summary['schema_version']}: {summary['calls']} calls, "
                        f"{summary['effects']} effects"
                    )
            else:
                fields = {k: v for k, v in data.items() if k != "schema_version"}
                contract = (
                    Contract(Report(**fields))
                    .require_triggered()
                    .no_duplicate_effects()
                    .at_most_calls(args.max_calls)
                )
                summaries.append(contract.to_dict())
                all_passed = all_passed and contract.passed
                if not args.json:
                    print("PASS" if contract.passed else "FAIL")
                    for check in contract.checks:
                        print(f"{'✓' if check.passed else '✗'} {check.name}: {check.detail}")
        if args.json:
            print(json.dumps(summaries[0] if len(summaries) == 1 else {"runs": summaries}))
        return 0 if all_passed else 1
    except (ToolstormError, ValueError, OSError, UnicodeError) as exc:
        # Parser errors are actionable; never dump trace data or arbitrary exception messages.
        print(f"toolstorm: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
