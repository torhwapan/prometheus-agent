"""Inspection plan construction and validation."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from .metric_catalog import apply_query_scope, select_metric_specs
from .target_resolver import resolve_target


MAX_RANGE_HOURS = 168
MIN_STEP_SECONDS = 15
MAX_ITEMS = 100


def build_inspection_plan(
    target_hint: str,
    domain: str,
    env: Optional[str] = None,
    instance_hint: Optional[str] = None,
    metric_ids: Optional[Sequence[str]] = None,
    range_hours: Optional[float] = None,
    step_seconds: Optional[int] = None,
    forecast_hours: Optional[float] = None,
    mode: str = "interactive",
    targets_config: str = "configs/targets.example.json",
    catalog_dir: str = "configs/metric_catalog",
) -> Dict[str, Any]:
    """Build an inspection plan from a natural target hint and metric domain."""
    resolved = resolve_target(
        target_hint=target_hint,
        domain=domain,
        env=env,
        instance_hint=instance_hint,
        targets_config=targets_config,
    )
    if not resolved.get("ok"):
        return resolved

    selected = select_metric_specs(domain=domain, metric_ids=metric_ids, catalog_dir=catalog_dir)
    if not selected.get("ok"):
        return selected

    scope = resolved["query_scope"]
    items = apply_query_scope(
        selected["items"],
        job_patterns=scope.get("job_patterns"),
        instance_hint=scope.get("instance_hint"),
    )
    plan = {
        "ok": True,
        "plan": {
            "mode": mode,
            "target": resolved["target"],
            "scope": {
                "domain": domain,
                "instance_hint": instance_hint,
                "job_patterns": scope.get("job_patterns", []),
            },
            "time": {
                "current_window": "5m",
                "range_hours": float(range_hours if range_hours is not None else scope["range_hours"]),
                "step_seconds": int(step_seconds if step_seconds is not None else scope["step_seconds"]),
                "forecast_hours": float(
                    forecast_hours if forecast_hours is not None else scope["forecast_hours"]
                ),
            },
            "items": items,
        },
        "warnings": resolved.get("warnings", []),
    }
    validation = validate_inspection_plan(plan["plan"])
    if not validation["ok"]:
        return validation
    return plan


def validate_inspection_plan(plan: Mapping[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    target = plan.get("target") if isinstance(plan.get("target"), Mapping) else {}
    time_cfg = plan.get("time") if isinstance(plan.get("time"), Mapping) else {}
    items = plan.get("items") if isinstance(plan.get("items"), list) else []

    if not target.get("id"):
        errors.append("target.id is required")
    if not target.get("base_url"):
        errors.append("target.base_url is required")

    range_hours = _float_or_none(time_cfg.get("range_hours"))
    step_seconds = _int_or_none(time_cfg.get("step_seconds"))
    forecast_hours = _float_or_none(time_cfg.get("forecast_hours"))
    if range_hours is None or range_hours <= 0 or range_hours > MAX_RANGE_HOURS:
        errors.append(f"time.range_hours must be between 0 and {MAX_RANGE_HOURS}")
    if step_seconds is None or step_seconds < MIN_STEP_SECONDS:
        errors.append(f"time.step_seconds must be at least {MIN_STEP_SECONDS}")
    if forecast_hours is None or forecast_hours < 0:
        errors.append("time.forecast_hours cannot be negative")

    if not items:
        errors.append("items must contain at least one metric")
    if len(items) > MAX_ITEMS:
        errors.append(f"items cannot contain more than {MAX_ITEMS} metrics")

    seen = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"items[{index}] must be an object")
            continue
        item_id = str(item.get("id") or "")
        if not item_id:
            errors.append(f"items[{index}].id is required")
        if item_id in seen:
            errors.append(f"duplicate item id: {item_id}")
        seen.add(item_id)
        if not item.get("range_promql") and not item.get("promql"):
            errors.append(f"items[{index}].range_promql is required")
        if not item.get("current_promql") and not item.get("promql"):
            errors.append(f"items[{index}].current_promql is required")
        direction = str(item.get("direction") or "higher_is_bad")
        if direction not in {"higher_is_bad", "lower_is_bad"}:
            errors.append(f"items[{index}].direction is invalid")

    if errors:
        return {"ok": False, "error": "invalid_inspection_plan", "errors": errors}
    return {"ok": True, "errors": []}


def plan_to_runner_config(plan: Mapping[str, Any]) -> Dict[str, Any]:
    """Convert InspectionPlan to the existing run_inspection config shape."""
    validation = validate_inspection_plan(plan)
    if not validation["ok"]:
        raise ValueError("; ".join(validation["errors"]))

    target = plan["target"]
    time_cfg = plan["time"]
    items = []
    for item in plan["items"]:
        normalized = dict(item)
        normalized["promql"] = str(normalized.get("range_promql") or normalized.get("promql"))
        items.append(normalized)

    return {
        "prometheus": {
            "base_url": target["base_url"],
            "headers": target.get("headers", {}),
            "timeout_seconds": float(target.get("timeout_seconds", 20)),
        },
        "inspection": {
            "range_hours": float(time_cfg["range_hours"]),
            "step_seconds": int(time_cfg["step_seconds"]),
            "forecast_hours": float(time_cfg["forecast_hours"]),
            "top_n_series": int(time_cfg.get("top_n_series", 10)),
            "min_points": int(time_cfg.get("min_points", 4)),
        },
        "items": items,
    }


def _float_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
