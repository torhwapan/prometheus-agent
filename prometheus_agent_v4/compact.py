"""Compact Prometheus query results for file-backed processing."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Mapping, Sequence, Tuple


def compact_task_result(
    result: Mapping[str, Any],
    max_points_per_series: int = 60,
) -> List[Dict[str, Any]]:
    task = result.get("task", {})
    current_by_key = {
        _series_key(series.get("labels", {})): _last_value(series.get("points", []))
        for series in result.get("current", [])
        if isinstance(series, Mapping)
    }
    compacted = []
    for series in result.get("range", []):
        if not isinstance(series, Mapping):
            continue
        labels = series.get("labels", {}) if isinstance(series.get("labels"), Mapping) else {}
        points = series.get("points", []) if isinstance(series.get("points"), list) else []
        values = [_value(point) for point in points]
        values = [value for value in values if value is not None and math.isfinite(value)]
        current = current_by_key.get(_series_key(labels))
        if current is None and values:
            current = values[-1]
        sampled = _sample_points(points, max_points_per_series)
        compacted.append(
            {
                "job": task.get("job"),
                "instance": labels.get("instance") or task.get("instance"),
                "metric_id": task.get("metric_id"),
                "metric_name": task.get("metric_name"),
                "series_labels": labels,
                "raw_point_count": len(points),
                "current": current,
                "summary": _summary(points, values),
                "sampled_points": sampled,
                "task": task,
                "ok": result.get("ok", True),
                "errors": result.get("errors", []),
            }
        )
    if not compacted and not result.get("ok", True):
        compacted.append(
            {
                "job": task.get("job"),
                "instance": task.get("instance"),
                "metric_id": task.get("metric_id"),
                "metric_name": task.get("metric_name"),
                "series_labels": {},
                "raw_point_count": 0,
                "current": None,
                "summary": {},
                "sampled_points": [],
                "task": task,
                "ok": False,
                "errors": result.get("errors", []),
            }
        )
    return compacted


def compact_to_analysis_result(compact: Mapping[str, Any]) -> Dict[str, Any]:
    task = dict(compact.get("task", {}))
    labels = compact.get("series_labels", {})
    return {
        "task": task,
        "ok": compact.get("ok", True),
        "current": [
            {
                "labels": labels,
                "points": [
                    {
                        "timestamp": compact.get("summary", {}).get("last_timestamp"),
                        "value": compact.get("current"),
                    }
                ]
                if compact.get("current") is not None
                else [],
            }
        ],
        "range": [
            {
                "labels": labels,
                "points": compact.get("sampled_points", []),
            }
        ],
        "errors": compact.get("errors", []),
    }


def ai_batch_item(compact: Mapping[str, Any], analysis_item: Mapping[str, Any] | None) -> Dict[str, Any]:
    return {
        "job": compact.get("job"),
        "instance": compact.get("instance"),
        "metric_id": compact.get("metric_id"),
        "metric_name": compact.get("metric_name"),
        "series_labels": compact.get("series_labels", {}),
        "python_severity": analysis_item.get("severity") if analysis_item else "unknown",
        "python_reason": analysis_item.get("reason") if analysis_item else None,
        "python_analysis": analysis_item.get("analysis") if analysis_item else {},
        "raw_point_count": compact.get("raw_point_count"),
        "summary": compact.get("summary", {}),
        "sampled_points": compact.get("sampled_points", []),
    }


def _summary(points: Sequence[Mapping[str, Any]], values: Sequence[float]) -> Dict[str, Any]:
    if not values:
        return {"point_count": 0}
    parsed = _parse_points(points)
    return {
        "point_count": len(values),
        "first": values[0],
        "last": values[-1],
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "p95": _percentile(values, 95),
        "first_timestamp": parsed[0][0].isoformat().replace("+00:00", "Z") if parsed else None,
        "last_timestamp": parsed[-1][0].isoformat().replace("+00:00", "Z") if parsed else None,
        "slope_per_hour": _slope_per_hour(parsed),
    }


def _sample_points(points: Sequence[Mapping[str, Any]], limit: int) -> List[Dict[str, Any]]:
    valid = [dict(point) for point in points if isinstance(point, Mapping)]
    if limit <= 0 or len(valid) <= limit:
        return valid
    if limit == 1:
        return [valid[-1]]
    indexes = sorted({round(i * (len(valid) - 1) / (limit - 1)) for i in range(limit)})
    return [valid[index] for index in indexes]


def _parse_points(points: Sequence[Mapping[str, Any]]) -> List[Tuple[datetime, float]]:
    parsed = []
    for point in points:
        try:
            parsed.append((datetime.fromisoformat(str(point["timestamp"]).replace("Z", "+00:00")), float(point["value"])))
        except (KeyError, TypeError, ValueError):
            continue
    return parsed


def _slope_per_hour(points: Sequence[Tuple[datetime, float]]) -> float:
    if len(points) < 2:
        return 0.0
    first = points[0][0].timestamp()
    xs = [point[0].timestamp() - first for point in points]
    ys = [point[1] for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    return 0.0 if denominator == 0 else numerator / denominator * 3600


def _percentile(values: Sequence[float], percentile: float) -> float:
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _series_key(labels: Mapping[str, Any]) -> Tuple[Tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in labels.items()))


def _last_value(points: Sequence[Mapping[str, Any]]) -> float | None:
    if not points:
        return None
    return _value(points[-1])


def _value(point: Mapping[str, Any]) -> float | None:
    try:
        return float(point["value"])
    except (KeyError, TypeError, ValueError):
        return None
