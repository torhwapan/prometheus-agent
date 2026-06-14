"""Execute v2 Prometheus query tasks one by one."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .models import MetricQueryTask, to_plain
from .prometheus import PrometheusClient, PrometheusQueryError


def execute_plan(
    plan: Mapping[str, Any],
    timeout_seconds: float = 20,
    headers: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Execute every query task and record each result independently."""
    client = PrometheusClient(
        base_url=str(plan["prometheus_url"]),
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    results = []
    for task in plan["tasks"]:
        results.append(execute_task(client, task))
    return {"ok": True, "results": results}


def execute_task(client: PrometheusClient, task: MetricQueryTask) -> Dict[str, Any]:
    record = {
        "task": to_plain(task),
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
            for item in client.query(task.current_promql, time=task.end)
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
                task.range_promql,
                start=task.start,
                end=task.end,
                step_seconds=task.step_seconds,
            )
        ]
    except PrometheusQueryError as exc:
        record["ok"] = False
        record["errors"].append({"stage": "range", "message": str(exc)})
    return record
