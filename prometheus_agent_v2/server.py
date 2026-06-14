"""CLI entry point for the v2 HTTP service."""

from __future__ import annotations

import argparse

from .service import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Prometheus Agent v2 HTTP service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
