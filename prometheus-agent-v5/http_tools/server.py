from __future__ import annotations

import argparse

try:
    from .service import run_server
except ImportError:
    from service import run_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Prometheus Agent V5 HTTP tools.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
