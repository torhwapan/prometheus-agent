from __future__ import annotations

import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prometheus_agent_v2.analysis import analyze_query_results  # noqa: E402
from prometheus_agent_v2.catalog import catalog_summary, load_catalog, normalize_job, select_specs  # noqa: E402
from prometheus_agent_v2.models import MetricSpec  # noqa: E402
from prometheus_agent_v2.planner import build_query_plan  # noqa: E402
from prometheus_agent_v2.prometheus import PrometheusQueryError  # noqa: E402
from prometheus_agent_v2.query import execute_plan  # noqa: E402

try:
    from .discovery import PrometheusDiscoveryClient
    from .semantics import resolve_semantic_payload, semantic_summary
except ImportError:
    from discovery import PrometheusDiscoveryClient
    from semantics import resolve_semantic_payload, semantic_summary


HandlerResult = Tuple[int, Dict[str, Any]]


class PrometheusAgentV5HttpApp:
    def __init__(self) -> None:
        self.routes: Dict[Tuple[str, str], Callable[[Mapping[str, Any]], HandlerResult]] = {
            ("GET", "/health"): self.health,
            ("GET", "/v5/catalog"): self.catalog,
            ("GET", "/v5/semantics"): self.semantics,
            ("POST", "/v5/query/inspection"): self.query_inspection,
            ("POST", "/v5/query/filter"): self.query_filter,
            ("POST", "/v5/query/topn"): self.query_topn,
            ("POST", "/v5/query/discovery"): self.query_discovery,
        }

    def dispatch(self, method: str, path: str, payload: Mapping[str, Any]) -> HandlerResult:
        route = self.routes.get((method, path))
        if route is None:
            return 404, {"ok": False, "error": "not_found", "path": path}
        try:
            return route(payload)
        except PrometheusQueryError as exc:
            return 502, {"ok": False, "error": "prometheus_query_failed", "message": str(exc)}
        except Exception as exc:
            return 500, {"ok": False, "error": "internal_error", "message": str(exc)}

    def health(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "service": "prometheus-agent-v5-http-tools"}

    def catalog(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "catalog": catalog_summary(load_catalog(payload.get("catalog_path")))}

    def semantics(self, payload: Mapping[str, Any]) -> HandlerResult:
        return 200, {"ok": True, "semantics": semantic_summary()}

    def query_inspection(self, payload: Mapping[str, Any]) -> HandlerResult:
        resolved_result = resolve_semantic_payload(payload, expected_mode="inspection")
        if not resolved_result.get("ok"):
            return 400, dict(resolved_result)
        resolved = resolved_result["resolved"]
        plan_result = self._build_plan(payload, resolved)
        if not plan_result.get("ok"):
            return 400, plan_result
        query_result = execute_plan(
            plan_result["plan"],
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=_headers(payload),
        )
        analysis = analyze_query_results(query_result["results"])
        items = _analysis_rows(analysis)
        risky_items = [item for item in items if item["severity"] != "ok"]
        return 200, {
            "ok": True,
            "mode": "inspection",
            "request": _request_summary(payload, resolved),
            "plan": plan_result["plain"],
            "summary": {
                "severity": analysis.get("severity"),
                "counts": analysis.get("counts"),
                "risky_count": len(risky_items),
            },
            "items": items,
            "risky_items": risky_items,
            "analysis": analysis,
        }

    def query_filter(self, payload: Mapping[str, Any]) -> HandlerResult:
        resolved_result = resolve_semantic_payload(payload, expected_mode="metric_filter")
        if not resolved_result.get("ok"):
            return 400, dict(resolved_result)
        resolved = resolved_result["resolved"]
        if resolved.get("threshold") is None or not resolved.get("comparison"):
            return 400, {"ok": False, "error": "comparison_and_threshold_required"}
        plan_result = self._build_plan(payload, resolved)
        if not plan_result.get("ok"):
            return 400, plan_result
        query_result = execute_plan(
            plan_result["plan"],
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=_headers(payload),
        )
        rows = _series_rows(query_result["results"], str(resolved.get("value_source") or "current"))
        matched = [row for row in rows if _compare(row["selected_value"], str(resolved["comparison"]), float(resolved["threshold"]))]
        matched = _sort_rows(matched, str(resolved.get("order") or "desc"))
        return 200, {
            "ok": True,
            "mode": "metric_filter",
            "request": _request_summary(payload, resolved),
            "metric": _metric_meta(resolved["job"], resolved["metric_ids"][0], payload.get("catalog_path")),
            "matched_count": len(matched),
            "items": matched,
            "items_all": rows if bool(payload.get("include_all_rows", False)) else None,
        }

    def query_topn(self, payload: Mapping[str, Any]) -> HandlerResult:
        resolved_result = resolve_semantic_payload(payload, expected_mode="metric_topn")
        if not resolved_result.get("ok"):
            return 400, dict(resolved_result)
        resolved = resolved_result["resolved"]
        top_n = int(resolved.get("top_n") or 10)
        plan_result = self._build_plan(payload, resolved)
        if not plan_result.get("ok"):
            return 400, plan_result
        query_result = execute_plan(
            plan_result["plan"],
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
            headers=_headers(payload),
        )
        rows = _series_rows(query_result["results"], str(resolved.get("value_source") or "current"))
        rows = _sort_rows(rows, str(resolved.get("order") or "desc"))
        selected = rows[:top_n]
        return 200, {
            "ok": True,
            "mode": "metric_topn",
            "request": _request_summary(payload, resolved),
            "metric": _metric_meta(resolved["job"], resolved["metric_ids"][0], payload.get("catalog_path")),
            "top_n": top_n,
            "items": selected,
        }

    def query_discovery(self, payload: Mapping[str, Any]) -> HandlerResult:
        prometheus_url = _prometheus_url(payload)
        if not prometheus_url:
            return 400, {"ok": False, "error": "prometheus_url_required"}
        action = str(payload.get("action") or "").strip()
        if not action:
            return 400, {"ok": False, "error": "action_required"}
        client = PrometheusDiscoveryClient(
            base_url=prometheus_url,
            headers=_headers(payload),
            timeout_seconds=float(payload.get("timeout_seconds", 20)),
        )
        if action == "job_values":
            data = client.job_values()
        elif action == "metric_names":
            data = client.metric_names()
        elif action == "label_values":
            label = str(payload.get("label") or "").strip()
            if not label:
                return 400, {"ok": False, "error": "label_required"}
            data = client.label_values(label)
        elif action == "series":
            match = str(payload.get("match") or "").strip()
            if not match:
                return 400, {"ok": False, "error": "match_required"}
            data = client.series(match, start=payload.get("start"), end=payload.get("end"))
        elif action == "targets":
            data = client.targets()
        elif action == "alerts":
            data = client.alerts()
        elif action == "metadata":
            metric = str(payload.get("metric") or "").strip() or None
            data = client.metadata(metric)
        else:
            return 400, {"ok": False, "error": "unsupported_action", "action": action}
        return 200, {
            "ok": True,
            "mode": "discovery",
            "prometheus_url": prometheus_url,
            "action": action,
            "data": data,
        }

    def _build_plan(self, payload: Mapping[str, Any], resolved: Mapping[str, Any]) -> Dict[str, Any]:
        return build_query_plan(
            prometheus_url=_prometheus_url(payload) or "",
            job=normalize_job(str(resolved["job"])),
            instance=str(resolved["instance"]) if resolved.get("instance") else None,
            range_hours=float(resolved["range_hours"]),
            step_seconds=int(resolved["step_seconds"]),
            current_window=str(resolved["current_window"]),
            metric_ids=list(resolved["metric_ids"]),
            catalog_path=payload.get("catalog_path"),
        )


def run_server(host: str = "127.0.0.1", port: int = 8050) -> None:
    app = PrometheusAgentV5HttpApp()

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
    print(f"prometheus-agent-v5 http tools listening on http://{host}:{port}")
    server.serve_forever()


def _prometheus_url(payload: Mapping[str, Any]) -> str:
    return str(payload.get("prometheus_url") or "").rstrip("/")


def _headers(payload: Mapping[str, Any]) -> Optional[Mapping[str, str]]:
    headers = payload.get("headers")
    return headers if isinstance(headers, Mapping) else None


def _request_summary(payload: Mapping[str, Any], resolved: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "prometheus_url": _prometheus_url(payload),
        "semantic_key": resolved.get("semantic_key"),
        "job": normalize_job(str(resolved.get("job") or "")),
        "instance": resolved.get("instance"),
        "metric_ids": list(resolved.get("metric_ids") or []),
        "range_hours": resolved.get("range_hours"),
        "step_seconds": resolved.get("step_seconds"),
        "current_window": resolved.get("current_window"),
        "comparison": resolved.get("comparison"),
        "threshold": resolved.get("threshold"),
        "top_n": resolved.get("top_n"),
        "value_source": resolved.get("value_source"),
    }


def _analysis_rows(analysis: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in analysis.get("items", []):
        row = {
            "job": item.get("job"),
            "instance": item.get("instance"),
            "metric_id": item.get("metric_id"),
            "metric_name": item.get("metric_name"),
            "severity": item.get("severity"),
            "current_value": item.get("current_value"),
            "reason": item.get("reason"),
            "labels": item.get("series_labels"),
            "analysis": item.get("analysis"),
        }
        unit = ""
        if isinstance(item.get("analysis"), Mapping):
            unit = str(item["analysis"].get("unit") or "")
        row["unit"] = unit
        rows.append(row)
    return rows


def _series_rows(query_results: Sequence[Mapping[str, Any]], value_source: str = "current") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in query_results:
        task = result.get("task", {})
        spec = task.get("spec", {})
        current_by_key = {
            _series_key(series.get("labels", {})): _last_value(series.get("points", []))
            for series in result.get("current", [])
            if isinstance(series, Mapping)
        }
        for series in result.get("range", []):
            if not isinstance(series, Mapping):
                continue
            labels = dict(series.get("labels", {}))
            points = _parse_points(series.get("points", []))
            values = [value for _, value in points]
            current_value = current_by_key.get(_series_key(labels))
            if current_value is None and values:
                current_value = values[-1]
            avg_value = sum(values) / len(values) if values else None
            min_value = min(values) if values else None
            max_value = max(values) if values else None
            selected_value = _pick_value(value_source, current_value=current_value, avg_value=avg_value, min_value=min_value, max_value=max_value)
            row = {
                "job": task.get("job"),
                "instance": labels.get("instance") or task.get("instance"),
                "metric_id": task.get("metric_id"),
                "metric_name": task.get("metric_name"),
                "labels": labels,
                "current_value": current_value,
                "avg_value": avg_value,
                "min_value": min_value,
                "max_value": max_value,
                "sample_count": len(values),
                "latest_timestamp": points[-1][0].isoformat().replace("+00:00", "Z") if points else None,
                "selected_value": selected_value,
                "selected_value_source": value_source,
                "unit": spec.get("unit", ""),
                "warning": spec.get("warning"),
                "critical": spec.get("critical"),
                "direction": spec.get("direction", "higher_is_bad"),
            }
            rows.append(row)
    return rows


def _metric_meta(job: str, metric_id: str, catalog_path: Any) -> Dict[str, Any]:
    catalog = load_catalog(catalog_path)
    specs = select_specs(catalog, job=normalize_job(job), metric_ids=[metric_id])
    if not specs:
        return {"job": normalize_job(job), "metric_id": metric_id}
    spec = specs[0]
    assert isinstance(spec, MetricSpec)
    return {
        "job": spec.job,
        "metric_id": spec.id,
        "metric_name": spec.name,
        "unit": spec.unit,
        "warning": spec.warning,
        "critical": spec.critical,
        "direction": spec.direction,
    }


def _parse_points(points: Sequence[Mapping[str, Any]]) -> List[Tuple[datetime, float]]:
    parsed: List[Tuple[datetime, float]] = []
    for point in points:
        try:
            parsed.append((datetime.fromisoformat(str(point["timestamp"]).replace("Z", "+00:00")), float(point["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    return parsed


def _last_value(points: Sequence[Mapping[str, Any]]) -> Optional[float]:
    if not points:
        return None
    try:
        return float(points[-1]["value"])
    except (KeyError, TypeError, ValueError):
        return None


def _series_key(labels: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _compare(value: Any, comparison: str, threshold: float) -> bool:
    if value is None:
        return False
    current = float(value)
    if comparison == ">":
        return current > threshold
    if comparison == ">=":
        return current >= threshold
    if comparison == "<":
        return current < threshold
    if comparison == "<=":
        return current <= threshold
    return False


def _sortable(value: Any) -> float:
    if value is None:
        return float("-inf")
    return float(value)


def _pick_value(
    value_source: str,
    *,
    current_value: Optional[float],
    avg_value: Optional[float],
    min_value: Optional[float],
    max_value: Optional[float],
) -> Optional[float]:
    if value_source == "avg":
        return avg_value
    if value_source == "min":
        return min_value
    if value_source == "max":
        return max_value
    return current_value


def _sort_rows(items: Sequence[Dict[str, Any]], order: str) -> List[Dict[str, Any]]:
    order_lower = order.lower()
    present = [item for item in items if item.get("selected_value") is not None]
    missing = [item for item in items if item.get("selected_value") is None]
    present.sort(key=lambda item: _sortable(item["selected_value"]), reverse=order_lower != "asc")
    return present + missing
