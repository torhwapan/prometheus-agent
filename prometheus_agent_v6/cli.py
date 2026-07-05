"""CLI for standalone Prometheus inspection V6."""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional

from .llm import LlmSettings
from .service import inspect_prometheus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone Prometheus fixed inspection V6")
    parser.add_argument("--prometheus-url", required=True, help="Prometheus base URL, for example http://127.0.0.1:9090")
    parser.add_argument("--output", default="report_v6.html", help="Output HTML path")
    parser.add_argument("--instance", help="Optional instance filter")
    parser.add_argument("--job", action="append", dest="jobs", help="Optional fixed inspection job, repeatable")
    parser.add_argument("--header", action="append", dest="headers", help="Optional request header in KEY=VALUE form")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--disable-ai", action="store_true", help="Disable optional LLM enrichment")
    parser.add_argument("--llm-base-url", help="Override LLM base URL, for example https://api.openai.com/v1")
    parser.add_argument("--llm-api-key", help="Override LLM API key")
    parser.add_argument("--llm-model", help="Override LLM model name")
    parser.add_argument("--print-json", action="store_true", help="Print structured result JSON to stdout")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    llm_settings = _build_llm_settings(args.llm_base_url, args.llm_api_key, args.llm_model)
    result = inspect_prometheus(
        args.prometheus_url,
        instance=args.instance,
        jobs=args.jobs,
        headers=_parse_headers(args.headers),
        timeout_seconds=args.timeout_seconds,
        output_path=args.output,
        llm_settings=llm_settings,
        enable_ai=not args.disable_ai,
    )

    if args.print_json:
        print(json.dumps(result["result"], ensure_ascii=False, indent=2))
    else:
        print(f"HTML report written to {args.output}")
        print(
            "Summary:",
            json.dumps(result["result"]["summary"], ensure_ascii=False),
        )
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
