"""Prometheus inspection agent toolkit."""

from .analysis import analyze_item, analyze_items
from .inspection_plan import build_inspection_plan, plan_to_runner_config, validate_inspection_plan
from .metric_catalog import load_metric_catalog, select_metric_specs
from .platform_tools import (
    build_inspection_plan_tool,
    grafana_threshold_tool,
    list_metric_domains_tool,
    list_targets_tool,
    metric_catalog_tool,
    run_inspection_plan_tool,
    target_resolver_tool,
    validate_inspection_plan_tool,
)
from .prometheus import PrometheusClient, PrometheusError, query_prometheus_range
from .report import generate_html_report
from .runner import run_inspection
from .target_resolver import resolve_target

__all__ = [
    "PrometheusClient",
    "PrometheusError",
    "analyze_item",
    "analyze_items",
    "build_inspection_plan",
    "build_inspection_plan_tool",
    "generate_html_report",
    "grafana_threshold_tool",
    "list_metric_domains_tool",
    "list_targets_tool",
    "load_metric_catalog",
    "metric_catalog_tool",
    "plan_to_runner_config",
    "query_prometheus_range",
    "resolve_target",
    "run_inspection",
    "run_inspection_plan_tool",
    "select_metric_specs",
    "target_resolver_tool",
    "validate_inspection_plan",
    "validate_inspection_plan_tool",
]
