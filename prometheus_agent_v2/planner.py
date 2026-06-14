"""Build v2 query tasks from user intent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .catalog import load_catalog, normalize_job, select_specs
from .models import MetricQueryTask, MetricSpec, to_plain


def build_query_plan(
    prometheus_url: str,
    job: Optional[str] = None,
    instance: Optional[str] = None,
    range_hours: float = 24,
    step_seconds: int = 60,
    current_window: str = "5m",
    metric_ids: Optional[Sequence[str]] = None,
    catalog_path: Optional[str] = None,
    end_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Create per-job, per-instance, per-metric query tasks."""
    if not prometheus_url:
        return {"ok": False, "error": "prometheus_url_required"}
    if range_hours <= 0:
        return {"ok": False, "error": "range_hours_must_be_positive"}
    if step_seconds <= 0:
        return {"ok": False, "error": "step_seconds_must_be_positive"}

    catalog = load_catalog(catalog_path)
    normalized_job = normalize_job(job) if job else None
    specs = select_specs(catalog, job=normalized_job, metric_ids=metric_ids)
    if not specs:
        return {
            "ok": False,
            "error": "no_metric_specs",
            "available_jobs": sorted(catalog.keys()),
        }

    end = end_time or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(hours=range_hours)

    tasks = [
        _task_from_spec(
            spec=spec,
            instance=instance,
            start=start,
            end=end,
            step_seconds=step_seconds,
            current_window=current_window,
        )
        for spec in specs
    ]
    return {
        "ok": True,
        "plan": {
            "prometheus_url": prometheus_url.rstrip("/"),
            "job": normalized_job,
            "instance": instance,
            "range_hours": range_hours,
            "step_seconds": step_seconds,
            "current_window": current_window,
            "start": start,
            "end": end,
            "tasks": tasks,
        },
        "plain": {
            "prometheus_url": prometheus_url.rstrip("/"),
            "job": normalized_job,
            "instance": instance,
            "range_hours": range_hours,
            "step_seconds": step_seconds,
            "current_window": current_window,
            "start": to_plain(start),
            "end": to_plain(end),
            "tasks": [to_plain(task) for task in tasks],
        },
    }


def plan_from_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return build_query_plan(
        prometheus_url=str(payload.get("prometheus_url") or ""),
        job=payload.get("job"),
        instance=payload.get("instance"),
        range_hours=float(payload.get("range_hours", 24)),
        step_seconds=int(payload.get("step_seconds", 60)),
        current_window=str(payload.get("current_window") or "5m"),
        metric_ids=payload.get("metric_ids") if isinstance(payload.get("metric_ids"), list) else None,
        catalog_path=payload.get("catalog_path"),
    )


def _task_from_spec(
    spec: MetricSpec,
    instance: Optional[str],
    start: datetime,
    end: datetime,
    step_seconds: int,
    current_window: str,
) -> MetricQueryTask:
    current_promql = spec.current_promql.replace("[5m]", f"[{current_window}]")
    range_promql = spec.range_promql.replace("[5m]", f"[{current_window}]")
    current_promql = _apply_instance_filter(current_promql, instance)
    range_promql = _apply_instance_filter(range_promql, instance)
    instance_part = instance or "all"
    return MetricQueryTask(
        task_id=f"{spec.job}:{instance_part}:{spec.id}",
        job=spec.job,
        metric_id=spec.id,
        metric_name=spec.name,
        instance=instance,
        current_promql=current_promql,
        range_promql=range_promql,
        start=start,
        end=end,
        step_seconds=step_seconds,
        spec=spec,
    )


def _apply_instance_filter(promql: str, instance: Optional[str]) -> str:
    if not instance:
        return promql
    label = f'instance=~".*{_escape(instance)}.*"'
    stripped = promql.strip()
    if not stripped:
        return promql
    if "{" in stripped:
        return stripped.replace("{", "{" + label + ",", 1)
    if "(" in stripped or " " in stripped or "/" in stripped or "*" in stripped or "-" in stripped or "+" in stripped:
        return promql
    return f"{stripped}{{{label}}}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
