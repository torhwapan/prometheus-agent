"""Skill entrypoint for Prometheus fixed inspection V7."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prometheus_agent_v6.llm import LlmSettings  # noqa: E402
from prometheus_agent_v6.service import inspect_prometheus  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run fixed Prometheus inspection and generate HTML report.")
    parser.add_argument("--prometheus-url", required=True, help="Prometheus base URL, for example http://127.0.0.1:9090")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--instance", help="Optional instance filter")
    parser.add_argument("--job", action="append", dest="jobs", help="Optional fixed inspection job, repeatable")
    parser.add_argument("--header", action="append", dest="headers", help="Optional request header in KEY=VALUE form")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--disable-ai", action="store_true", help="Disable optional LLM enrichment")
    parser.add_argument("--llm-base-url", help="Override LLM base URL")
    parser.add_argument("--llm-api-key", help="Override LLM API key")
    parser.add_argument("--llm-model", help="Override LLM model")
    parser.add_argument("--print-json", action="store_true", help="Print structured inspection result JSON")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    result = inspect_prometheus(
        args.prometheus_url,
        instance=args.instance,
        jobs=args.jobs,
        headers=_parse_headers(args.headers),
        timeout_seconds=args.timeout_seconds,
        output_path=args.output,
        llm_settings=_build_llm_settings(args.llm_base_url, args.llm_api_key, args.llm_model),
        enable_ai=not args.disable_ai,
    )

    if args.print_json:
        print(json.dumps(result["result"], ensure_ascii=False, indent=2))
    else:
        print(f"HTML report written to {args.output}")
        print(json.dumps(result["result"]["summary"], ensure_ascii=False))
    return 0


def _parse_headers(values: Optional[List[str]]) -> Optional[Dict[str, str]]:
    if not values:
        return None
    headers: Dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"invalid header format: {item}")
        key, value = item.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def _build_llm_settings(base_url: Optional[str], api_key: Optional[str], model: Optional[str]) -> Optional[LlmSettings]:
    if base_url and api_key and model:
        return LlmSettings(base_url=base_url.rstrip("/"), api_key=api_key, model=model)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
