"""Stateful HTTP service for Prometheus inspection agent v3."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Mapping, Tuple

from prometheus_agent_v2.ai_inputs import build_ai_series_inputs, merge_ai_series_findings
from prometheus_agent_v2.analysis import analyze_query_results
from prometheus_agent_v2.catalog import catalog_summary, load_catalog
from prometheus_agent_v2.planner import plan_from_payload
from prometheus_agent_v2.query import execute_plan
from prometheus_agent_v2.report import render_html, render_markdown

from .store import InspectionStore


HandlerResult = Tuple[int, Dict[str, Any]]


class PrometheusAgentV3App:
    def __init__(self, store: InspectionStore | None = None) -> None:
        self.store = store or InspectionStore()
        self.routes: Dict[Tuple[str, str], Callable[[Mapping[str, Any]], HandlerResult]] = {
            ("GET", "/health"): self.health,
            ("GET", "/v3/catalog"): self.catalog,
            ("GET", "/v3/inspections"): self.list_inspections,
            ("POST", "/v3/inspections"): self.create_inspection,
            ("POST", "/v3/query"): self.query,
            ("POST", "/v3/analyze"): self.analyze,
            ("POST", "/v3/build-ai-series-inputs"): self.build_ai_series_inputs,
            ("POST", "/v3/merge-ai-series-findings"): self.merge_ai_series_findings,
            ("POST", "/v3/merge-ai-correlation"): self.merge_ai_correlation,
            ("POST", "/v3/report"): self.report,
            ("POST", "/v3/run-deterministic"): self.run_deterministic,
        }

    def dispatch(self, method: str, path: str, payload: Mapping[str, Any]) -> HandlerResult:
        route = self.routes.get((method, path))
        if route is None:
            if method == "GET" and path.startswith("/v3/inspections/"):
                return self.get_inspection(path.rsplit("/", 1)[-1])
            return 404, {"ok": False, "error": "not_found", "path": path}
        try:
            return route(payload)
        except Exception as exc:
            return 500, {"ok": False, "error": "internal_error", "message": str(exc)}

    def health(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "service": "prometheus-agent-v3"}

    def catalog(self, payload: Mapping[str, Any]) -> HandlerResult:
        catalog = load_catalog(payload.get("catalog_path"))
        return 200, {"ok": True, "catalog": catalog_summary(catalog)}

    def list_inspections(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "items": self.store.list()}

    def get_inspection(self, inspection_id: str) -> HandlerResult:
        record = self.store.get(inspection_id)
        if record is None:
            return 404, {"ok": False, "error": "inspection_not_found", "inspection_id": inspection_id}
        return 200, {"ok": True, "inspection": record}

    def create_inspection(self, payload: Mapping[str, Any]) -> HandlerResult:
        plan_result = plan_from_payload(payload)
        if not plan_result.get("ok"):
            return 400, plan_result
        record = self.store.create(intent=payload, plan_payload=plan_result)
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": record["status"],
            "plan_summary": _plan_summary(record.get("plain_plan")),
        }

    def query(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        plan = record.get("plan")
        if not isinstance(plan, Mapping):
            return 400, {"ok": False, "error": "plan_missing", "inspection_id": record["inspection_id"]}
        query_result = execute_plan(
            plan,
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=payload.get("headers") if isinstance(payload.get("headers"), Mapping) else None,
        )
        updated = self.store.update(record["inspection_id"], query=query_result, status="queried")
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "query_summary": _query_summary(query_result),
        }

    def analyze(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        query = record.get("query")
        if not isinstance(query, Mapping) or not isinstance(query.get("results"), list):
            return 400, {"ok": False, "error": "query_results_missing", "inspection_id": record["inspection_id"]}
        analysis = analyze_query_results(query["results"])
        updated = self.store.update(record["inspection_id"], analysis=analysis, status="analyzed")
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "analysis_summary": {
                "severity": analysis.get("severity"),
                "counts": analysis.get("counts"),
                "risky_count": len(analysis.get("risky_items", [])),
            },
        }

    def build_ai_series_inputs(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        query = record.get("query")
        analysis = record.get("analysis")
        if not isinstance(query, Mapping) or not isinstance(query.get("results"), list):
            return 400, {"ok": False, "error": "query_results_missing", "inspection_id": record["inspection_id"]}
        if not isinstance(analysis, Mapping):
            return 400, {"ok": False, "error": "analysis_missing", "inspection_id": record["inspection_id"]}
        ai_inputs = build_ai_series_inputs(
            query_results=query["results"],
            analysis=analysis,
            max_points_per_series=int(payload.get("max_points_per_series", 24)),
            risky_only=bool(payload.get("risky_only", False)),
        )
        updated = self.store.update(record["inspection_id"], ai_series_inputs=ai_inputs, status="ai_inputs_built")
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "items": ai_inputs["items"],
        }

    def merge_ai_series_findings(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        analysis = record.get("analysis")
        findings = payload.get("findings")
        if not isinstance(analysis, Mapping):
            return 400, {"ok": False, "error": "analysis_missing", "inspection_id": record["inspection_id"]}
        if not isinstance(findings, list):
            return 400, {"ok": False, "error": "findings_required"}
        merged = merge_ai_series_findings(analysis, findings)
        updated = self.store.update(
            record["inspection_id"],
            analysis=merged["analysis"],
            ai_series_findings=findings,
            status="ai_findings_merged",
        )
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "analysis_summary": _analysis_summary(merged["analysis"]),
        }

    def merge_ai_correlation(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        correlation = payload.get("ai_correlation")
        if not isinstance(correlation, Mapping):
            return 400, {"ok": False, "error": "ai_correlation_required"}
        updated = self.store.update(record["inspection_id"], ai_correlation=correlation, status="ai_correlation_merged")
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "ai_correlation": updated["ai_correlation"],
        }

    def report(self, payload: Mapping[str, Any]) -> HandlerResult:
        record, error = self._record(payload)
        if error:
            return error
        analysis = record.get("analysis")
        if not isinstance(analysis, Mapping):
            return 400, {"ok": False, "error": "analysis_missing", "inspection_id": record["inspection_id"]}
        fmt = str(payload.get("format") or "html").lower()
        ai_correlation = record.get("ai_correlation") if isinstance(record.get("ai_correlation"), Mapping) else None
        content = render_markdown(analysis, ai_correlation=ai_correlation) if fmt in {"md", "markdown"} else render_html(analysis, ai_correlation=ai_correlation)
        report = {
            "format": "markdown" if fmt in {"md", "markdown"} else "html",
            "content": content,
        }
        updated = self.store.update(record["inspection_id"], report=report, status="reported")
        return 200, {
            "ok": True,
            "inspection_id": record["inspection_id"],
            "status": updated["status"],
            "report": report,
        }

    def run_deterministic(self, payload: Mapping[str, Any]) -> HandlerResult:
        created_status, created = self.create_inspection(payload)
        if created_status != 200:
            return created_status, created
        inspection_id = created["inspection_id"]
        query_status, query_payload = self.query({"inspection_id": inspection_id, **dict(payload)})
        if query_status != 200:
            return query_status, query_payload
        analysis_status, analysis_payload = self.analyze({"inspection_id": inspection_id})
        if analysis_status != 200:
            return analysis_status, analysis_payload
        report_status, report_payload = self.report({"inspection_id": inspection_id, "format": payload.get("format", "html")})
        if report_status != 200:
            return report_status, report_payload
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "query_summary": query_payload.get("query_summary"),
            "analysis_summary": analysis_payload.get("analysis_summary"),
            "report": report_payload.get("report"),
        }

    def _record(self, payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], HandlerResult | None]:
        inspection_id = str(payload.get("inspection_id") or "")
        if not inspection_id:
            return {}, (400, {"ok": False, "error": "inspection_id_required"})
        record = self.store.get(inspection_id)
        if record is None:
            return {}, (404, {"ok": False, "error": "inspection_not_found", "inspection_id": inspection_id})
        return record, None


def create_app() -> PrometheusAgentV3App:
    return PrometheusAgentV3App()


def run_server(host: str = "127.0.0.1", port: int = 8020) -> None:
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
    print(f"prometheus-agent-v3 listening on http://{host}:{port}")
    server.serve_forever()


def _plan_summary(plan: Any) -> Dict[str, Any]:
    if not isinstance(plan, Mapping):
        return {}
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    return {
        "prometheus_url": plan.get("prometheus_url"),
        "job": plan.get("job"),
        "instance": plan.get("instance"),
        "range_hours": plan.get("range_hours"),
        "step_seconds": plan.get("step_seconds"),
        "task_count": len(tasks),
    }


def _query_summary(query: Mapping[str, Any]) -> Dict[str, Any]:
    results = query.get("results") if isinstance(query.get("results"), list) else []
    failed = [item for item in results if not item.get("ok")]
    return {"task_count": len(results), "failed_count": len(failed)}


def _analysis_summary(analysis: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "severity": analysis.get("severity"),
        "counts": analysis.get("counts"),
        "risky_count": len(analysis.get("risky_items", [])) if isinstance(analysis.get("risky_items"), list) else 0,
    }
