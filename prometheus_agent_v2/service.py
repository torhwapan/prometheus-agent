"""HTTP service exposing v2 Prometheus inspection tools."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Mapping, Tuple

from .ai_inputs import build_ai_series_inputs, merge_ai_series_findings
from .analysis import analyze_query_results
from .catalog import catalog_summary, load_catalog
from .planner import plan_from_payload
from .query import execute_plan
from .report import render_html, render_markdown


HandlerResult = Tuple[int, Dict[str, Any]]


class PrometheusAgentV2App:
    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], Callable[[Mapping[str, Any]], HandlerResult]] = {
            ("GET", "/health"): self.health,
            ("GET", "/v2/catalog"): self.catalog,
            ("POST", "/v2/plan"): self.plan,
            ("POST", "/v2/query"): self.query,
            ("POST", "/v2/analyze"): self.analyze,
            ("POST", "/v2/build-ai-series-inputs"): self.build_ai_series_inputs,
            ("POST", "/v2/merge-ai-series-findings"): self.merge_ai_series_findings,
            ("POST", "/v2/merge-ai-comments"): self.merge_ai_comments,
            ("POST", "/v2/report"): self.report,
            ("POST", "/v2/run"): self.run,
        }

    def dispatch(self, method: str, path: str, payload: Mapping[str, Any]) -> HandlerResult:
        route = self.routes.get((method, path))
        if route is None:
            return 404, {"ok": False, "error": "not_found", "path": path}
        try:
            return route(payload)
        except Exception as exc:
            return 500, {"ok": False, "error": "internal_error", "message": str(exc)}

    def health(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "service": "prometheus-agent-v2"}

    def catalog(self, payload: Mapping[str, Any]) -> HandlerResult:
        catalog = load_catalog(payload.get("catalog_path"))
        return 200, {"ok": True, "catalog": catalog_summary(catalog)}

    def plan(self, payload: Mapping[str, Any]) -> HandlerResult:
        result = plan_from_payload(payload)
        return (200 if result.get("ok") else 400), result

    def query(self, payload: Mapping[str, Any]) -> HandlerResult:
        plan = payload.get("plan")
        if not isinstance(plan, Mapping):
            plan_result = plan_from_payload(payload)
            if not plan_result.get("ok"):
                return 400, plan_result
            plan = plan_result["plan"]
        result = execute_plan(
            plan,
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=payload.get("headers") if isinstance(payload.get("headers"), Mapping) else None,
        )
        return 200, result

    def analyze(self, payload: Mapping[str, Any]) -> HandlerResult:
        query_results = payload.get("results")
        if not isinstance(query_results, list):
            return 400, {"ok": False, "error": "results_required"}
        return 200, analyze_query_results(query_results)

    def build_ai_series_inputs(self, payload: Mapping[str, Any]) -> HandlerResult:
        query_results = payload.get("results")
        analysis = payload.get("analysis")
        if not isinstance(query_results, list) or not isinstance(analysis, Mapping):
            return 400, {"ok": False, "error": "results_and_analysis_required"}
        result = build_ai_series_inputs(
            query_results=query_results,
            analysis=analysis,
            max_points_per_series=int(payload.get("max_points_per_series", 24)),
            risky_only=bool(payload.get("risky_only", False)),
        )
        return 200, result

    def merge_ai_series_findings(self, payload: Mapping[str, Any]) -> HandlerResult:
        analysis = payload.get("analysis")
        findings = payload.get("findings")
        if not isinstance(analysis, Mapping) or not isinstance(findings, list):
            return 400, {"ok": False, "error": "analysis_and_findings_required"}
        return 200, merge_ai_series_findings(analysis, findings)

    def merge_ai_comments(self, payload: Mapping[str, Any]) -> HandlerResult:
        analysis = payload.get("analysis")
        comments = payload.get("comments")
        if not isinstance(analysis, Mapping) or not isinstance(comments, list):
            return 400, {"ok": False, "error": "analysis_and_comments_required"}
        by_key = {
            (
                str(item.get("job")),
                str(item.get("instance")),
                str(item.get("metric_id")),
            ): str(item.get("comment") or "")
            for item in comments
        }
        merged = dict(analysis)
        merged_items = []
        for item in analysis.get("items", []):
            updated = dict(item)
            key = (str(updated.get("job")), str(updated.get("instance")), str(updated.get("metric_id")))
            if key in by_key:
                updated["ai_comment"] = by_key[key]
            merged_items.append(updated)
        merged["items"] = merged_items
        merged["risky_items"] = [item for item in merged_items if item.get("severity") != "ok"]
        return 200, {"ok": True, "analysis": merged}

    def report(self, payload: Mapping[str, Any]) -> HandlerResult:
        analysis = payload.get("analysis")
        if not isinstance(analysis, Mapping):
            return 400, {"ok": False, "error": "analysis_required"}
        ai_correlation = payload.get("ai_correlation") if isinstance(payload.get("ai_correlation"), Mapping) else None
        fmt = str(payload.get("format") or "html").lower()
        if fmt == "md" or fmt == "markdown":
            content = render_markdown(analysis, ai_correlation=ai_correlation)
            return 200, {"ok": True, "format": "markdown", "content": content}
        content = render_html(analysis, ai_correlation=ai_correlation)
        return 200, {"ok": True, "format": "html", "content": content}

    def run(self, payload: Mapping[str, Any]) -> HandlerResult:
        plan_result = plan_from_payload(payload)
        if not plan_result.get("ok"):
            return 400, plan_result
        query_result = execute_plan(
            plan_result["plan"],
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=payload.get("headers") if isinstance(payload.get("headers"), Mapping) else None,
        )
        analysis = analyze_query_results(query_result["results"])
        fmt = str(payload.get("format") or "html").lower()
        content = render_markdown(analysis) if fmt in {"md", "markdown"} else render_html(analysis)
        return 200, {
            "ok": True,
            "plan": plan_result["plain"],
            "query": query_result,
            "analysis": analysis,
            "report": {
                "format": "markdown" if fmt in {"md", "markdown"} else "html",
                "content": content,
            },
        }


def create_app() -> PrometheusAgentV2App:
    return PrometheusAgentV2App()


def run_server(host: str = "127.0.0.1", port: int = 8010) -> None:
    app = create_app()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def _handle(self, method: str) -> None:
            payload = self._read_json() if method == "POST" else {}
            status, body = app.dispatch(method, self.path.split("?", 1)[0], payload)
            raw = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            if not raw.strip():
                return {}
            return json.loads(raw)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"prometheus-agent-v2 listening on http://{host}:{port}")
    server.serve_forever()
