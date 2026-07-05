"""Build fixed inspection query plans for V6."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .models import InspectionPack, MetricSpec, QueryTask, to_plain


def build_plan(
    prometheus_url: str,
    packs: Sequence[InspectionPack],
    catalog: Mapping[str, Sequence[MetricSpec]],
    instance: Optional[str] = None,
    end_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    if not prometheus_url:
        return {"ok": False, "error": "prometheus_url_required"}
    if not packs:
        return {"ok": True, "plan": {"prometheus_url": prometheus_url.rstrip("/"), "tasks": []}, "plain": {"prometheus_url": prometheus_url.rstrip("/"), "tasks": []}}

    end = end_time or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    tasks: List[QueryTask] = []
    for pack in packs:
        specs_by_id = {spec.id: spec for spec in catalog.get(pack.job, [])}
        for metric_id in pack.metric_ids:
            spec = specs_by_id.get(metric_id)
            if spec is None:
                continue
            current_window = spec.current_window or pack.current_window
            step_seconds = spec.step_seconds or pack.step_seconds
            range_hours = spec.range_hours or pack.range_hours
            start = end - timedelta(hours=float(range_hours))
            current_promql = _apply_instance_filter(_replace_window(spec.current_promql, current_window), instance)
            range_promql = _apply_instance_filter(_replace_window(spec.range_promql, current_window), instance)
            tasks.append(
                QueryTask(
                    task_id=f"{pack.key}:{spec.job}:{instance or 'all'}:{spec.id}",
                    pack_key=pack.key,
                    pack_title=pack.title,
                    job=spec.job,
                    metric_id=spec.id,
                    metric_name=spec.name,
                    instance=instance,
                    current_promql=current_promql,
                    range_promql=range_promql,
                    start=start,
                    end=end,
                    step_seconds=int(step_seconds),
                    spec=spec,
                )
            )

    starts = [task.start for task in tasks]
    plan = {
        "prometheus_url": prometheus_url.rstrip("/"),
        "instance": instance,
        "start": min(starts) if starts else end,
        "end": end,
        "packs": list(packs),
        "tasks": tasks,
    }
    return {"ok": True, "plan": plan, "plain": to_plain(plan)}


def _replace_window(promql: str, current_window: str) -> str:
    return promql.replace("[5m]", f"[{current_window}]")


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
