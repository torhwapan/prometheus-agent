"""Deterministic metric analysis for v2."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .models import SEVERITY_ORDER, max_severity


def analyze_query_results(query_results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    analyses = []
    for result in query_results:
        analyses.extend(_analyze_task_result(result))
    risky = [item for item in analyses if item["severity"] in {"info", "warning", "critical", "unknown"}]
    severity = max_severity([item["severity"] for item in analyses])
    return {
        "ok": True,
        "severity": severity,
        "items": sorted(analyses, key=_sort_key, reverse=True),
        "risky_items": sorted(risky, key=_sort_key, reverse=True),
        "counts": _counts(analyses),
    }


def _analyze_task_result(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    task = result["task"]
    spec = task["spec"]
    if not result.get("ok"):
        return [
            {
                "job": task["job"],
                "instance": task.get("instance"),
                "metric_id": task["metric_id"],
                "metric_name": task["metric_name"],
                "series_labels": {},
                "severity": "unknown",
                "reason": "; ".join(error["message"] for error in result.get("errors", [])),
                "analysis": {},
                "current_value": None,
                "ai_comment": None,
            }
        ]

    current_by_key = {
        _series_key(series["labels"]): _last_value(series.get("points", []))
        for series in result.get("current", [])
    }
    range_series = result.get("range", [])
    if not range_series:
        return [
            {
                "job": task["job"],
                "instance": task.get("instance"),
                "metric_id": task["metric_id"],
                "metric_name": task["metric_name"],
                "series_labels": {},
                "severity": "unknown",
                "reason": "No range samples returned.",
                "analysis": {},
                "current_value": None,
                "ai_comment": None,
            }
        ]

    analyses = []
    for series in range_series:
        labels = series.get("labels", {})
        points = _parse_points(series.get("points", []))
        current_value = current_by_key.get(_series_key(labels))
        if current_value is None:
            current_value = points[-1][1] if points else None
        analysis = _analyze_points(points, current_value, spec)
        analyses.append(
            {
                "job": task["job"],
                "instance": labels.get("instance") or task.get("instance"),
                "metric_id": task["metric_id"],
                "metric_name": task["metric_name"],
                "series_labels": labels,
                "severity": analysis["severity"],
                "reason": analysis["reason"],
                "analysis": analysis,
                "current_value": current_value,
                "ai_comment": None,
            }
        )
    return analyses


def _analyze_points(
    points: Sequence[Tuple[datetime, float]],
    current_value: Optional[float],
    spec: Mapping[str, Any],
) -> Dict[str, Any]:
    values = [value for _, value in points if math.isfinite(value)]
    if len(values) < 4:
        return {
            "severity": "unknown",
            "reason": f"Only {len(values)} usable samples.",
            "point_count": len(values),
        }

    current = current_value if current_value is not None else values[-1]
    minimum = min(values)
    maximum = max(values)
    average = sum(values) / len(values)
    p95 = _percentile(values, 95)
    slope_per_hour = _slope_per_hour(points)
    forecast_24h = current + slope_per_hour * 24
    threshold_severity = _threshold_severity(current, spec)
    forecast_severity = _threshold_severity(forecast_24h, spec)
    burst = _burst_detected(values)
    sustained_growth = _sustained_growth(values, spec)
    time_to_limit = _time_to_limit(current, slope_per_hour, spec)

    severity = max_severity([threshold_severity, forecast_severity])
    reasons = []
    if threshold_severity in {"warning", "critical"}:
        reasons.append(f"Current value is already {threshold_severity}.")
    if forecast_severity in {"warning", "critical"} and forecast_severity != threshold_severity:
        reasons.append(f"24h forecast may reach {forecast_severity}.")
    if burst:
        severity = _raise_to_at_least(severity, "warning")
        reasons.append("Recent samples show a burst.")
    if sustained_growth:
        severity = _raise_to_at_least(severity, "info")
        reasons.append("Series is continuously growing without clear slowdown.")
    if time_to_limit is not None and time_to_limit <= 24:
        severity = _raise_to_at_least(severity, "warning")
        reasons.append(f"Estimated time to limit is {time_to_limit:.1f}h.")
    if not reasons:
        reasons.append("No obvious threshold breach, burst, or sustained growth risk.")

    return {
        "severity": severity,
        "reason": " ".join(reasons),
        "point_count": len(values),
        "current": current,
        "min": minimum,
        "max": maximum,
        "avg": average,
        "p95": p95,
        "slope_per_hour": slope_per_hour,
        "forecast_24h": forecast_24h,
        "burst": burst,
        "sustained_growth": sustained_growth,
        "time_to_limit_hours": time_to_limit,
        "warning": spec.get("warning"),
        "critical": spec.get("critical"),
        "max_value": spec.get("max_value"),
        "unit": spec.get("unit", ""),
    }


def _threshold_severity(value: Optional[float], spec: Mapping[str, Any]) -> str:
    if value is None:
        return "unknown"
    direction = spec.get("direction", "higher_is_bad")
    warning = spec.get("warning")
    critical = spec.get("critical")
    if direction == "lower_is_bad":
        if critical is not None and value <= float(critical):
            return "critical"
        if warning is not None and value <= float(warning):
            return "warning"
        return "ok"
    if critical is not None and value >= float(critical):
        return "critical"
    if warning is not None and value >= float(warning):
        return "warning"
    return "ok"


def _burst_detected(values: Sequence[float]) -> bool:
    if len(values) < 8:
        return False
    midpoint = max(1, len(values) // 2)
    early = values[:midpoint]
    late = values[midpoint:]
    early_avg = sum(early) / len(early)
    late_avg = sum(late) / len(late)
    if abs(early_avg) < 1e-9:
        return late_avg > 0
    return (late_avg - early_avg) / abs(early_avg) >= 0.5


def _sustained_growth(values: Sequence[float], spec: Mapping[str, Any]) -> bool:
    if spec.get("direction", "higher_is_bad") != "higher_is_bad":
        return False
    if len(values) < 6:
        return False
    increases = 0
    total = 0
    for before, after in zip(values, values[1:]):
        if after >= before:
            increases += 1
        total += 1
    return total > 0 and increases / total >= 0.8 and values[-1] > values[0]


def _time_to_limit(
    current: float,
    slope_per_hour: float,
    spec: Mapping[str, Any],
) -> Optional[float]:
    if slope_per_hour <= 0:
        return None
    limit = spec.get("max_value") or spec.get("critical") or spec.get("warning")
    if limit is None:
        return None
    limit = float(limit)
    if current >= limit:
        return 0.0
    hours = (limit - current) / slope_per_hour
    return hours if math.isfinite(hours) and hours >= 0 else None


def _slope_per_hour(points: Sequence[Tuple[datetime, float]]) -> float:
    if len(points) < 2:
        return 0.0
    first = points[0][0].timestamp()
    xs = [item[0].timestamp() - first for item in points]
    ys = [item[1] for item in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator * 3600


def _percentile(values: Sequence[float], percentile: float) -> float:
    sorted_values = sorted(values)
    rank = (len(sorted_values) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _parse_points(points: Sequence[Mapping[str, Any]]) -> List[Tuple[datetime, float]]:
    parsed = []
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


def _raise_to_at_least(current: str, minimum: str) -> str:
    if SEVERITY_ORDER.get(current, 0) < SEVERITY_ORDER.get(minimum, 0):
        return minimum
    return current


def _counts(items: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"critical": 0, "warning": 0, "info": 0, "ok": 0, "unknown": 0}
    for item in items:
        severity = str(item.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _sort_key(item: Mapping[str, Any]) -> Tuple[int, float]:
    severity = SEVERITY_ORDER.get(str(item.get("severity")), -1)
    current = item.get("current_value")
    return severity, abs(float(current)) if current is not None else -1.0
