"""Metric catalog loading and filtering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


DEFAULT_CATALOG_DIR = "configs/metric_catalog"


def list_metric_domains(catalog_dir: str = DEFAULT_CATALOG_DIR) -> Dict[str, Any]:
    path = Path(catalog_dir)
    domains = sorted(item.stem for item in path.glob("*.json"))
    return {"ok": True, "domains": domains}


def load_metric_catalog(
    domains: Optional[Sequence[str]] = None,
    catalog_dir: str = DEFAULT_CATALOG_DIR,
) -> Dict[str, Any]:
    """Load metric specs by domain from JSON catalog files."""
    requested = list(domains or _discover_domains(catalog_dir))
    loaded: Dict[str, Any] = {}
    missing: List[str] = []
    for domain in requested:
        path = Path(catalog_dir) / f"{domain}.json"
        if not path.exists():
            missing.append(domain)
            continue
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        items = raw.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"metric catalog {path} must contain an items list")
        loaded[domain] = [_normalize_metric(domain, item) for item in items if isinstance(item, Mapping)]
    return {"ok": not missing, "catalog": loaded, "missing_domains": missing}


def select_metric_specs(
    domain: str,
    metric_ids: Optional[Sequence[str]] = None,
    catalog_dir: str = DEFAULT_CATALOG_DIR,
) -> Dict[str, Any]:
    """Return selected metric specs for a domain."""
    payload = load_metric_catalog([domain], catalog_dir=catalog_dir)
    if domain not in payload["catalog"]:
        return {
            "ok": False,
            "error": "domain_not_found",
            "message": f"No metric catalog found for domain {domain!r}.",
            "available_domains": list_metric_domains(catalog_dir)["domains"],
        }
    specs = payload["catalog"][domain]
    if metric_ids:
        wanted = set(metric_ids)
        specs = [spec for spec in specs if spec["id"] in wanted]
        missing = sorted(wanted - {spec["id"] for spec in specs})
    else:
        missing = []
    return {"ok": not missing, "domain": domain, "items": specs, "missing_metric_ids": missing}


def apply_query_scope(
    metric_specs: Sequence[Mapping[str, Any]],
    job_patterns: Optional[Sequence[str]] = None,
    instance_hint: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Apply simple label filters to catalog PromQL.

    This intentionally only injects selectors for straightforward metric names.
    Complex catalog queries should already contain their own labels.
    """
    scoped = []
    label_filter = _label_filter(job_patterns=job_patterns, instance_hint=instance_hint)
    for spec in metric_specs:
        item = dict(spec)
        if label_filter:
            item["current_promql"] = _inject_filter(str(item["current_promql"]), label_filter)
            item["range_promql"] = _inject_filter(str(item["range_promql"]), label_filter)
        item["promql"] = item["range_promql"]
        scoped.append(item)
    return scoped


def _discover_domains(catalog_dir: str) -> List[str]:
    return sorted(path.stem for path in Path(catalog_dir).glob("*.json"))


def _normalize_metric(domain: str, item: Mapping[str, Any]) -> Dict[str, Any]:
    metric = dict(item)
    metric["domain"] = str(metric.get("domain") or domain)
    metric["id"] = str(metric.get("id") or metric.get("name"))
    metric["name"] = str(metric.get("name") or metric["id"])
    metric["description"] = str(metric.get("description") or "")
    metric["current_promql"] = str(metric.get("current_promql") or metric.get("promql") or "")
    metric["range_promql"] = str(metric.get("range_promql") or metric.get("promql") or metric["current_promql"])
    metric["promql"] = metric["range_promql"]
    metric["value_type"] = str(metric.get("value_type") or "number")
    metric["unit"] = str(metric.get("unit") or "")
    metric["analysis_type"] = str(metric.get("analysis_type") or "threshold_trend")
    metric["direction"] = str(metric.get("direction") or "higher_is_bad")
    metric["threshold_source"] = str(metric.get("threshold_source") or "catalog")
    return metric


def _label_filter(
    job_patterns: Optional[Sequence[str]],
    instance_hint: Optional[str],
) -> str:
    labels = []
    patterns = [pattern for pattern in (job_patterns or []) if pattern]
    if patterns:
        if len(patterns) == 1:
            labels.append(f'job=~".*{_escape_label_value(patterns[0])}.*"')
        else:
            joined = "|".join(f".*{_escape_label_value(pattern)}.*" for pattern in patterns)
            labels.append(f'job=~"{joined}"')
    if instance_hint:
        labels.append(f'instance=~".*{_escape_label_value(instance_hint)}.*"')
    return ",".join(labels)


def _inject_filter(query: str, label_filter: str) -> str:
    stripped = query.strip()
    if not stripped or "{" in stripped or "(" in stripped or " " in stripped or "/" in stripped:
        return query
    return f"{stripped}{{{label_filter}}}"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
