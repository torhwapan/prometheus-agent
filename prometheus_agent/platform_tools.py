"""Stable tool functions intended for AI-platform integration."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from .grafana import merge_thresholds, query_grafana_thresholds
from .inspection_plan import build_inspection_plan, plan_to_runner_config, validate_inspection_plan
from .metric_catalog import list_metric_domains, select_metric_specs
from .runner import run_inspection
from .target_resolver import list_targets, resolve_target


def target_resolver_tool(
    target_hint: str,
    domain: Optional[str] = None,
    env: Optional[str] = None,
    instance_hint: Optional[str] = None,
    targets_config: str = "configs/targets.example.json",
) -> Dict[str, Any]:
    return resolve_target(
        target_hint=target_hint,
        domain=domain,
        env=env,
        instance_hint=instance_hint,
        targets_config=targets_config,
    )


def list_targets_tool(targets_config: str = "configs/targets.example.json") -> Dict[str, Any]:
    return list_targets(targets_config=targets_config)


def metric_catalog_tool(
    domain: str,
    metric_ids: Optional[Sequence[str]] = None,
    catalog_dir: str = "configs/metric_catalog",
) -> Dict[str, Any]:
    return select_metric_specs(domain=domain, metric_ids=metric_ids, catalog_dir=catalog_dir)


def list_metric_domains_tool(catalog_dir: str = "configs/metric_catalog") -> Dict[str, Any]:
    return list_metric_domains(catalog_dir=catalog_dir)


def build_inspection_plan_tool(
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
    return build_inspection_plan(
        target_hint=target_hint,
        domain=domain,
        env=env,
        instance_hint=instance_hint,
        metric_ids=metric_ids,
        range_hours=range_hours,
        step_seconds=step_seconds,
        forecast_hours=forecast_hours,
        mode=mode,
        targets_config=targets_config,
        catalog_dir=catalog_dir,
    )


def grafana_threshold_tool(
    resolved_target: Mapping[str, Any],
    metric_ids: Optional[Sequence[str]] = None,
    timeout_seconds: float = 20,
) -> Dict[str, Any]:
    grafana = resolved_target.get("grafana") if isinstance(resolved_target, Mapping) else None
    if not isinstance(grafana, Mapping):
        return {"ok": False, "error": "grafana_not_configured", "thresholds": []}
    return query_grafana_thresholds(
        grafana=grafana,
        metric_ids=metric_ids,
        timeout_seconds=timeout_seconds,
    )


def validate_inspection_plan_tool(plan: Mapping[str, Any]) -> Dict[str, Any]:
    return validate_inspection_plan(plan)


def run_inspection_plan_tool(
    plan: Mapping[str, Any],
    output_path: Optional[str] = None,
    use_grafana_thresholds: bool = True,
) -> Dict[str, Any]:
    """Run a validated InspectionPlan and return structured result plus report."""
    validation = validate_inspection_plan(plan)
    if not validation["ok"]:
        return validation

    executable_plan = dict(plan)
    items = [dict(item) for item in executable_plan["items"]]
    threshold_payload = {"ok": False, "thresholds": []}
    if use_grafana_thresholds:
        threshold_payload = grafana_threshold_tool(
            resolved_target=executable_plan.get("target", {}),
            metric_ids=[str(item.get("id")) for item in items],
        )
        if threshold_payload.get("thresholds"):
            items = merge_thresholds(items, threshold_payload["thresholds"])
    executable_plan["items"] = items

    config = plan_to_runner_config(executable_plan)
    payload = run_inspection(config, output_path=output_path)
    payload["thresholds"] = threshold_payload
    payload["plan"] = executable_plan
    return payload
