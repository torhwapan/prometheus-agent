"""Configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Union


DEFAULT_INSPECTION = {
    "range_hours": 24,
    "step_seconds": 300,
    "forecast_hours": 24,
    "top_n_series": 10,
    "min_points": 4,
}


ConfigInput = Union[str, Path, Mapping[str, Any]]


def load_config(config: ConfigInput) -> Dict[str, Any]:
    if isinstance(config, Mapping):
        raw = dict(config)
    else:
        path = Path(config)
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    return normalize_config(raw)


def normalize_config(raw: Mapping[str, Any]) -> Dict[str, Any]:
    config = dict(raw)
    prometheus = config.get("prometheus")
    if not isinstance(prometheus, MutableMapping):
        raise ValueError("config.prometheus is required")
    if not prometheus.get("base_url"):
        raise ValueError("config.prometheus.base_url is required")

    items = config.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("config.items must contain at least one inspection item")

    normalized_items = []
    seen_ids = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, MutableMapping):
            raise ValueError(f"config.items[{index}] must be an object")
        normalized = dict(item)
        item_id = str(normalized.get("id") or normalized.get("name") or f"item_{index}")
        if item_id in seen_ids:
            raise ValueError(f"Duplicate inspection item id: {item_id}")
        seen_ids.add(item_id)
        normalized["id"] = item_id
        if not normalized.get("name"):
            normalized["name"] = item_id
        if not (normalized.get("promql") or normalized.get("query")):
            raise ValueError(f"Inspection item {item_id} must define promql")
        normalized["promql"] = str(normalized.get("promql") or normalized.get("query"))
        normalized["direction"] = str(normalized.get("direction") or "higher_is_bad")
        if normalized["direction"] not in {"higher_is_bad", "lower_is_bad"}:
            raise ValueError(
                f"Inspection item {item_id} direction must be higher_is_bad or lower_is_bad"
            )
        normalized_items.append(normalized)

    inspection = dict(DEFAULT_INSPECTION)
    if isinstance(config.get("inspection"), MutableMapping):
        inspection.update(config["inspection"])
    inspection["range_hours"] = float(inspection["range_hours"])
    inspection["step_seconds"] = int(inspection["step_seconds"])
    inspection["forecast_hours"] = float(inspection["forecast_hours"])
    inspection["top_n_series"] = int(inspection["top_n_series"])
    inspection["min_points"] = int(inspection["min_points"])
    if inspection["range_hours"] <= 0:
        raise ValueError("inspection.range_hours must be positive")
    if inspection["step_seconds"] <= 0:
        raise ValueError("inspection.step_seconds must be positive")
    if inspection["forecast_hours"] < 0:
        raise ValueError("inspection.forecast_hours cannot be negative")
    if inspection["top_n_series"] <= 0:
        raise ValueError("inspection.top_n_series must be positive")
    if inspection["min_points"] < 2:
        raise ValueError("inspection.min_points must be at least 2")

    config["prometheus"] = dict(prometheus)
    config["inspection"] = inspection
    config["items"] = normalized_items
    return config
