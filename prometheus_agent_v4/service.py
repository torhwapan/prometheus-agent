"""File-backed HTTP service for Prometheus inspection agent v4."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Tuple

from prometheus_agent_v2.analysis import analyze_query_results
from prometheus_agent_v2.catalog import catalog_summary, load_catalog
from prometheus_agent_v2.models import to_plain
from prometheus_agent_v2.planner import plan_from_payload
from prometheus_agent_v2.prometheus import PrometheusClient, PrometheusQueryError

from .compact import ai_batch_item, compact_task_result, compact_to_analysis_result
from .files import DEFAULT_DATA_DIR, InspectionFiles, safe_part
from .report import render_html_report


HandlerResult = Tuple[int, Dict[str, Any]]


class PrometheusAgentV4App:
    def __init__(self, files: InspectionFiles | None = None) -> None:
        self.files = files or InspectionFiles(DEFAULT_DATA_DIR)
        self.routes: Dict[Tuple[str, str], Callable[[Mapping[str, Any]], HandlerResult]] = {
            ("GET", "/health"): self.health,
            ("GET", "/v4/catalog"): self.catalog,
            ("GET", "/v4/inspections"): self.list_inspections,
            ("POST", "/v4/inspections"): self.create_inspection,
            ("POST", "/v4/query-and-compact"): self.query_and_compact,
            ("POST", "/v4/analyze"): self.analyze,
            ("POST", "/v4/build-ai-batches"): self.build_ai_batches,
            ("POST", "/v4/list-ai-batches"): self.list_ai_batches,
            ("POST", "/v4/list-pending-ai-batches"): self.list_pending_ai_batches,
            ("POST", "/v4/get-ai-batch"): self.get_ai_batch,
            ("POST", "/v4/next-ai-batch"): self.next_ai_batch,
            ("POST", "/v4/merge-ai-batch-findings"): self.merge_ai_batch_findings,
            ("POST", "/v4/build-final-correlation-input"): self.build_final_correlation_input,
            ("POST", "/v4/merge-final-correlation"): self.merge_final_correlation,
            ("POST", "/v4/report"): self.report,
            ("POST", "/v4/run-deterministic"): self.run_deterministic,
        }

    def dispatch(self, method: str, path: str, payload: Mapping[str, Any]) -> HandlerResult:
        route = self.routes.get((method, path))
        if route is None:
            if method == "GET" and path.startswith("/v4/inspections/"):
                return self.get_inspection(path.rsplit("/", 1)[-1])
            return 404, {"ok": False, "error": "not_found", "path": path}
        try:
            return route(payload)
        except Exception as exc:
            return 500, {"ok": False, "error": "internal_error", "message": str(exc)}

    def health(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "service": "prometheus-agent-v4"}

    def catalog(self, payload: Mapping[str, Any]) -> HandlerResult:
        catalog = load_catalog(payload.get("catalog_path"))
        return 200, {"ok": True, "catalog": catalog_summary(catalog)}

    def list_inspections(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "items": self.files.list()}

    def get_inspection(self, inspection_id: str) -> HandlerResult:
        meta = self.files.meta(inspection_id)
        if meta is None:
            return 404, {"ok": False, "error": "inspection_not_found", "inspection_id": inspection_id}
        return 200, {"ok": True, "inspection": meta}

    def create_inspection(self, payload: Mapping[str, Any]) -> HandlerResult:
        plan_result = plan_from_payload(payload)
        if not plan_result.get("ok"):
            return 400, plan_result
        meta = self.files.create(payload, plan_result)
        plan_summary = _plan_summary(plan_result.get("plain"))
        meta["summary"]["plan"] = plan_summary
        self.files.write_json(meta["inspection_id"], "meta.json", meta)
        return 200, {
            "ok": True,
            "inspection_id": meta["inspection_id"],
            "status": meta["status"],
            "plan_summary": plan_summary,
            "base_path": meta["paths"]["base"],
        }

    def query_and_compact(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        plan = self.files.read_json(inspection_id, "plan.json")
        client = PrometheusClient(
            base_url=str(plan["prometheus_url"]),
            headers=payload.get("headers") if isinstance(payload.get("headers"), Mapping) else None,
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
        )
        max_points = int(payload.get("max_points_per_series", 60))
        summary = {
            "task_count": 0,
            "series_count": 0,
            "failed_count": 0,
            "raw_files": [],
            "compact_files": [],
        }
        for task in plan["tasks"]:
            summary["task_count"] += 1
            result = _execute_plain_task(client, task)
            if not result.get("ok"):
                summary["failed_count"] += 1
            raw_path = self._write_raw_result(inspection_id, result)
            summary["raw_files"].append(str(raw_path))
            compact_items = compact_task_result(result, max_points_per_series=max_points)
            summary["series_count"] += len(compact_items)
            for compact in compact_items:
                compact_path = self._write_compact_item(inspection_id, compact)
                summary["compact_files"].append(str(compact_path))
                self.files.append_jsonl(inspection_id, "compact/index.jsonl", {"path": str(compact_path), **_compact_index(compact)})
        meta = self.files.meta(inspection_id) or {}
        meta.setdefault("summary", {})["query"] = summary
        meta["status"] = "compacted"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {"ok": True, "inspection_id": inspection_id, "status": "compacted", "query_summary": summary}

    def analyze(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        compact_items = self._read_all_compact(inspection_id)
        analysis_inputs = [compact_to_analysis_result(item) for item in compact_items]
        analysis = analyze_query_results(analysis_inputs)
        self.files.write_json(inspection_id, "analysis/analysis.json", analysis)
        for item in analysis.get("items", []):
            self._write_analysis_item(inspection_id, item)
        meta = self.files.meta(inspection_id) or {}
        meta.setdefault("summary", {})["analysis"] = _analysis_summary(analysis)
        meta["status"] = "analyzed"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {"ok": True, "inspection_id": inspection_id, "status": "analyzed", "analysis_summary": _analysis_summary(analysis)}

    def build_ai_batches(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        risky_only = bool(payload.get("risky_only", False))
        compact_items = self._read_all_compact(inspection_id)
        analysis = self.files.read_json(inspection_id, "analysis/analysis.json")
        analysis_by_key = {_analysis_key(item): item for item in analysis.get("items", [])}
        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for compact in compact_items:
            item_analysis = analysis_by_key.get(_compact_key(compact))
            if risky_only and item_analysis and item_analysis.get("severity") == "ok":
                continue
            batch_key = (str(compact.get("job") or "unknown"), str(compact.get("instance") or "unknown"))
            grouped[batch_key].append(ai_batch_item(compact, item_analysis))
        batches = []
        for (job, instance), items in grouped.items():
            batch_id = f"{safe_part(job)}__{safe_part(instance)}"
            batch = {
                "inspection_id": inspection_id,
                "batch_id": batch_id,
                "job": job,
                "instance": instance,
                "item_count": len(items),
                "items": items,
            }
            path = self.files.write_json(inspection_id, f"ai_input/{batch_id}.json", batch)
            batches.append({"batch_id": batch_id, "job": job, "instance": instance, "item_count": len(items), "path": str(path)})
        meta = self.files.meta(inspection_id) or {}
        batch_records = self._ai_batch_records(inspection_id, include_content=False)
        meta.setdefault("summary", {})["ai_batches"] = {"batch_count": len(batches), "batches": batches}
        meta["summary"]["ai_batch_progress"] = self._ai_batch_progress(inspection_id, batch_records)
        meta["status"] = "ai_batches_built"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "status": "ai_batches_built",
            "batches": batches,
            "batch_progress": meta["summary"]["ai_batch_progress"],
        }

    def list_ai_batches(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        batches = self._ai_batch_records(inspection_id, include_content=bool(payload.get("include_content", False)))
        progress = self._ai_batch_progress(inspection_id, batches)
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "batches": batches,
            "batch_progress": progress,
        }

    def list_pending_ai_batches(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        batches = self._ai_batch_records(inspection_id, include_content=False)
        pending_ids = [str(batch.get("batch_id") or "") for batch in batches if not batch.get("completed")]
        progress = self._ai_batch_progress(inspection_id, batches)
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "batch_ids": pending_ids,
            "batch_progress": progress,
        }

    def get_ai_batch(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        batch_id = str(payload.get("batch_id") or "")
        if not batch_id:
            return 400, {"ok": False, "error": "batch_id_required"}
        path = self.files.base(inspection_id) / "ai_input" / f"{safe_part(batch_id)}.json"
        if not path.exists():
            return 404, {"ok": False, "error": "batch_not_found", "inspection_id": inspection_id, "batch_id": batch_id}
        batch = _read_json_if_exists(path)
        output_path = self.files.base(inspection_id) / "ai_output" / f"{safe_part(batch_id)}.json"
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "batch_id": batch_id,
            "completed": output_path.exists(),
            "batch": batch,
        }

    def next_ai_batch(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        batches = self._ai_batch_records(inspection_id, include_content=False)
        progress = self._ai_batch_progress(inspection_id, batches)
        for batch in batches:
            if not batch["completed"]:
                batch_payload = self.files.read_json(inspection_id, f"ai_input/{safe_part(batch['batch_id'])}.json")
                return 200, {
                    "ok": True,
                    "inspection_id": inspection_id,
                    "done": False,
                    "batch_progress": progress,
                    "batch": batch_payload,
                }
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "done": True,
            "batch_progress": progress,
            "batch": None,
        }

    def merge_ai_batch_findings(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        batch_id = str(payload.get("batch_id") or "")
        finding = payload.get("finding")
        findings = payload.get("findings")
        if not batch_id:
            return 400, {"ok": False, "error": "batch_id_required"}
        if finding is None and findings is None:
            return 400, {"ok": False, "error": "finding_or_findings_required"}
        input_path = self.files.base(inspection_id) / "ai_input" / f"{safe_part(batch_id)}.json"
        if not input_path.exists():
            return 404, {"ok": False, "error": "batch_not_found", "inspection_id": inspection_id, "batch_id": batch_id}
        output = {"batch_id": batch_id, "finding": finding, "findings": findings}
        path = self.files.write_json(inspection_id, f"ai_output/{safe_part(batch_id)}.json", output)
        meta = self.files.meta(inspection_id) or {}
        summary = meta.setdefault("summary", {})
        ai_outputs = summary.setdefault("ai_outputs", [])
        if not any(item.get("batch_id") == batch_id for item in ai_outputs if isinstance(item, Mapping)):
            ai_outputs.append({"batch_id": batch_id, "path": str(path)})
        batches = self._ai_batch_records(inspection_id, include_content=False)
        summary["ai_batch_progress"] = self._ai_batch_progress(inspection_id, batches)
        meta["status"] = "ai_batch_findings_merged"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {
            "ok": True,
            "inspection_id": inspection_id,
            "status": "ai_batch_findings_merged",
            "path": str(path),
            "batch_progress": summary["ai_batch_progress"],
        }

    def build_final_correlation_input(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        analysis = self.files.read_json(inspection_id, "analysis/analysis.json")
        batch_findings = self._read_ai_outputs(inspection_id)
        correlation_input = {
            "inspection_id": inspection_id,
            "severity": analysis.get("severity"),
            "counts": analysis.get("counts"),
            "risky_items": analysis.get("risky_items", []),
            "batch_findings": batch_findings,
        }
        path = self.files.write_json(inspection_id, "ai_input/final_correlation.json", correlation_input)
        return 200, {"ok": True, "inspection_id": inspection_id, "path": str(path), "input": correlation_input}

    def merge_final_correlation(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        correlation = payload.get("ai_correlation")
        if not isinstance(correlation, Mapping):
            return 400, {"ok": False, "error": "ai_correlation_required"}
        path = self.files.write_json(inspection_id, "ai_output/final_correlation.json", correlation)
        meta = self.files.meta(inspection_id) or {}
        meta.setdefault("summary", {})["ai_correlation"] = {"path": str(path), "summary": correlation.get("summary")}
        meta["status"] = "final_correlation_merged"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {"ok": True, "inspection_id": inspection_id, "status": "final_correlation_merged", "path": str(path)}

    def report(self, payload: Mapping[str, Any]) -> HandlerResult:
        inspection_id, error = self._inspection_id(payload)
        if error:
            return error
        analysis = self.files.read_json(inspection_id, "analysis/analysis.json")
        correlation_path = self.files.base(inspection_id) / "ai_output" / "final_correlation.json"
        ai_correlation = _read_json_if_exists(correlation_path)
        ai_batch_outputs = self._read_ai_outputs(inspection_id)
        fmt = str(payload.get("format") or "html").lower()
        content = render_html_report(
            analysis,
            plan=self.files.read_json(inspection_id, "plan.json"),
            meta=self.files.meta(inspection_id) or {},
            ai_correlation=ai_correlation,
            ai_batch_outputs=ai_batch_outputs,
        )
        extension = "md" if fmt in {"md", "markdown"} else "html"
        if extension == "md":
            content = self._render_markdown_report(analysis, ai_correlation=ai_correlation)
        relative = f"report/report.{extension}"
        path = self.files.base(inspection_id) / relative
        path.write_text(content, encoding="utf-8")
        meta = self.files.meta(inspection_id) or {}
        meta.setdefault("summary", {})["report"] = {"path": str(path), "format": extension}
        meta["status"] = "reported"
        self.files.write_json(inspection_id, "meta.json", meta)
        return 200, {"ok": True, "inspection_id": inspection_id, "status": "reported", "report": {"format": extension, "path": str(path), "content": content if bool(payload.get("include_content", True)) else None}}

    def run_deterministic(self, payload: Mapping[str, Any]) -> HandlerResult:
        create_status, create_payload = self.create_inspection(payload)
        if create_status != 200:
            return create_status, create_payload
        inspection_id = create_payload["inspection_id"]
        query_status, query_payload = self.query_and_compact({"inspection_id": inspection_id, **dict(payload)})
        if query_status != 200:
            return query_status, query_payload
        analysis_status, analysis_payload = self.analyze({"inspection_id": inspection_id})
        if analysis_status != 200:
            return analysis_status, analysis_payload
        report_status, report_payload = self.report({"inspection_id": inspection_id, "format": payload.get("format", "html")})
        if report_status != 200:
            return report_status, report_payload
        return 200, {"ok": True, "inspection_id": inspection_id, "query_summary": query_payload.get("query_summary"), "analysis_summary": analysis_payload.get("analysis_summary"), "report": report_payload.get("report")}

    def _inspection_id(self, payload: Mapping[str, Any]) -> Tuple[str, HandlerResult | None]:
        inspection_id = str(payload.get("inspection_id") or "")
        if not inspection_id:
            return "", (400, {"ok": False, "error": "inspection_id_required"})
        if not self.files.exists(inspection_id):
            return "", (404, {"ok": False, "error": "inspection_not_found", "inspection_id": inspection_id})
        return inspection_id, None

    def _write_raw_result(self, inspection_id: str, result: Mapping[str, Any]) -> Path:
        task = result.get("task", {})
        relative = f"raw/{safe_part(task.get('job'))}/{safe_part(task.get('metric_id'))}.json"
        return self.files.write_json(inspection_id, relative, result)

    def _write_compact_item(self, inspection_id: str, compact: Mapping[str, Any]) -> Path:
        relative = (
            f"compact/{safe_part(compact.get('job'))}/"
            f"{safe_part(compact.get('instance'))}/"
            f"{safe_part(compact.get('metric_id'))}.json"
        )
        return self.files.write_json(inspection_id, relative, compact)

    def _write_analysis_item(self, inspection_id: str, item: Mapping[str, Any]) -> Path:
        relative = (
            f"analysis/{safe_part(item.get('job'))}/"
            f"{safe_part(item.get('instance'))}/"
            f"{safe_part(item.get('metric_id'))}.json"
        )
        return self.files.write_json(inspection_id, relative, item)

    def _read_all_compact(self, inspection_id: str) -> List[Dict[str, Any]]:
        compact_root = self.files.base(inspection_id) / "compact"
        items = []
        for path in compact_root.rglob("*.json"):
            if path.name == "index.jsonl":
                continue
            with path.open("r", encoding="utf-8") as handle:
                items.append(json.load(handle))
        return items

    def _read_ai_outputs(self, inspection_id: str) -> List[Dict[str, Any]]:
        output_root = self.files.base(inspection_id) / "ai_output"
        outputs = []
        for path in output_root.glob("*.json"):
            if path.name == "final_correlation.json":
                continue
            with path.open("r", encoding="utf-8") as handle:
                outputs.append(json.load(handle))
        return outputs

    def _render_markdown_report(self, analysis: Mapping[str, Any], ai_correlation: Mapping[str, Any] | None = None) -> str:
        lines = [
            "# Prometheus 巡检报告",
            "",
            f"- 生成时间: {self._now_local()}",
            f"- 总体等级: {analysis.get('severity', 'unknown')}",
            f"- 统计: {analysis.get('counts', {})}",
            "",
        ]
        if ai_correlation:
            lines.extend(["## AI 关联性分析", "", str(ai_correlation.get("summary", "")), ""])
            for item in ai_correlation.get("correlations", []):
                lines.append(
                    f"- `{item.get('level')}` {item.get('jobs')} / {item.get('instances')}: {item.get('reason')}；建议：{item.get('suggestion')}"
                )
            lines.append("")
        for item in analysis.get("items", []):
            lines.extend([
                f"## {item.get('job')}/{item.get('instance')}",
                "",
                f"- 指标: {item.get('metric_name') or item.get('metric_id')}",
                f"- 等级: {item.get('severity')}",
                f"- 规则: {item.get('reason')}",
                f"- AI: {item.get('ai_comment') or ''}",
                "",
            ])
        return "\n".join(lines)

    def _now_local(self) -> str:
        return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _ai_batch_records(self, inspection_id: str, include_content: bool = False) -> List[Dict[str, Any]]:
        input_root = self.files.base(inspection_id) / "ai_input"
        output_root = self.files.base(inspection_id) / "ai_output"
        batches = []
        for path in sorted(input_root.glob("*.json")):
            if path.name == "final_correlation.json":
                continue
            batch = _read_json_if_exists(path) or {}
            batch_id = str(batch.get("batch_id") or path.stem)
            output_path = output_root / f"{safe_part(batch_id)}.json"
            record = {
                "batch_id": batch_id,
                "job": batch.get("job"),
                "instance": batch.get("instance"),
                "item_count": batch.get("item_count"),
                "path": str(path),
                "completed": output_path.exists(),
                "output_path": str(output_path) if output_path.exists() else None,
            }
            if include_content:
                record["batch"] = batch
            batches.append(record)
        return batches

    def _completed_ai_batch_ids(self, inspection_id: str) -> set[str]:
        output_root = self.files.base(inspection_id) / "ai_output"
        completed = set()
        for path in output_root.glob("*.json"):
            if path.name == "final_correlation.json":
                continue
            payload = _read_json_if_exists(path) or {}
            completed.add(str(payload.get("batch_id") or path.stem))
        return completed

    def _ai_batch_progress(self, inspection_id: str, batches: List[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
        records = batches if batches is not None else self._ai_batch_records(inspection_id, include_content=False)
        total = len(records)
        completed = sum(1 for item in records if item.get("completed"))
        return {
            "total": total,
            "completed": completed,
            "remaining": max(total - completed, 0),
            "done": completed >= total,
        }


def create_app(data_dir: str | None = None) -> PrometheusAgentV4App:
    files = InspectionFiles(data_dir) if data_dir else None
    return PrometheusAgentV4App(files)


def run_server(host: str = "127.0.0.1", port: int = 8030, data_dir: str | None = None) -> None:
    app = create_app(data_dir=data_dir)

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
            return json.loads(raw) if raw.strip() else {}

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"prometheus-agent-v4 listening on http://{host}:{port}, data_dir={app.files.root}")
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


def _analysis_summary(analysis: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "severity": analysis.get("severity"),
        "counts": analysis.get("counts"),
        "risky_count": len(analysis.get("risky_items", [])) if isinstance(analysis.get("risky_items"), list) else 0,
    }


def _compact_index(compact: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "job": compact.get("job"),
        "instance": compact.get("instance"),
        "metric_id": compact.get("metric_id"),
        "raw_point_count": compact.get("raw_point_count"),
    }


def _compact_key(compact: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (
        str(compact.get("job") or ""),
        str(compact.get("instance") or ""),
        str(compact.get("metric_id") or ""),
    )


def _analysis_key(item: Mapping[str, Any]) -> Tuple[str, str, str]:
    return (
        str(item.get("job") or ""),
        str(item.get("instance") or ""),
        str(item.get("metric_id") or ""),
    )


def _execute_plain_task(client: PrometheusClient, task: Mapping[str, Any]) -> Dict[str, Any]:
    record = {
        "task": dict(task),
        "ok": True,
        "current": [],
        "range": [],
        "errors": [],
    }
    try:
        record["current"] = [
            {
                "labels": item["labels"],
                "points": [to_plain(point) for point in item["points"]],
            }
            for item in client.query(str(task.get("current_promql") or ""), time=task.get("end"))
        ]
    except PrometheusQueryError as exc:
        record["ok"] = False
        record["errors"].append({"stage": "current", "message": str(exc)})

    try:
        record["range"] = [
            {
                "labels": item["labels"],
                "points": [to_plain(point) for point in item["points"]],
            }
            for item in client.query_range(
                str(task.get("range_promql") or ""),
                start=str(task.get("start") or ""),
                end=str(task.get("end") or ""),
                step_seconds=int(task.get("step_seconds") or 60),
            )
        ]
    except (PrometheusQueryError, TypeError, ValueError) as exc:
        record["ok"] = False
        record["errors"].append({"stage": "range", "message": str(exc)})
    return record


def _read_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
