"""Command line interface for the Prometheus inspection agent."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from .runner import run_inspection


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Prometheus predictive inspection.")
    parser.add_argument("--config", required=True, help="Path to JSON config file.")
    parser.add_argument(
        "--output",
        default="prometheus_inspection_report.html",
        help="HTML report output path.",
    )
    parser.add_argument("--end", help="Inspection end time, ISO-8601. Defaults to now.")
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print JSON-friendly inspection result to stdout.",
    )
    args = parser.parse_args(argv)

    try:
        payload = run_inspection(args.config, output_path=args.output, end=args.end)
    except Exception as exc:
        print(f"Inspection failed: {exc}", file=sys.stderr)
        return 1

    if args.print_json:
        print(json.dumps(payload["result"], ensure_ascii=False, indent=2))
    else:
        print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
