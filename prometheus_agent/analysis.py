"""Predictive inspection analysis for Prometheus time series."""

from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence, Tuple

from .models import ItemAnalysis, SEVERITY_ORDER, SeriesAnalysis, TimeSeries, max_severity


STATUS_BY_SEVERITY = {
    "critical": "Critical",
    "warning": "Warning",
    "unknown": "Unknown",
    "info": "Watch",
    "ok": "Healthy",
}


def analyze_items(
    items: Sequence[Mapping[str, object]],
    series_by_item_id: Mapping[str, Sequence[TimeSeries]],
    forecast_hours: float = 24,
    top_n_series: int = 10,
    min_points: int = 4,
) -> List[ItemAnalysis]:
    """Analyze all configured inspection items."""
    results = []
    for item in items:
        item_id = str(item.get("id") or item.get("name") or "item")
        results.append(
            analyze_item(
                item=item,
                series_list=series_by_item_id.get(item_id, []),
                forecast_hours=forecast_hours,
                top_n_series=top_n_series,
                min_points=min_points,
            )
        )
    return results


def analyze_item(
    item: Mapping[str, object],
    series_list: Sequence[TimeSeries],
    forecast_hours: float = 24,
    top_n_series: int = 10,
    min_points: int = 4,
) -> ItemAnalysis:
    """Analyze one inspection item across all returned time series."""
    item_id = str(item.get("id") or item.get("name") or "item")
    name = str(item.get("name") or item_id)
    description = str(item.get("description") or "")
    promql = str(item.get("promql") or item.get("query") or "")
    unit = str(item.get("unit") or "")

    if not series_list:
        return ItemAnalysis(
            id=item_id,
            name=name,
            description=description,
            promql=promql,
            unit=unit,
            severity="unknown",
            status=STATUS_BY_SEVERITY["unknown"],
            summary="Prometheus returned no time series for this item.",
            checked_series=0,
            returned_series=0,
            series=[],
        )

    analyses = [
        _analyze_series(item, series, forecast_hours=forecast_hours, min_points=min_points)
        for series in series_list
    ]
    analyses.sort(key=_series_sort_key, reverse=True)
    selected = analyses[:top_n_series]
    severity = max_severity(analysis.severity for analysis in analyses)
    summary = _item_summary(severity, analyses, len(series_list))

    return ItemAnalysis(
        id=item_id,
        name=name,
        description=description,
        promql=promql,
        unit=unit,
        severity=severity,
        status=STATUS_BY_SEVERITY.get(severity, severity.title()),
        summary=summary,
        checked_series=len(series_list),
        returned_series=len(selected),
        series=selected,
    )


def analysis_error_item(item: Mapping[str, object], message: str) -> ItemAnalysis:
    """Build an item result for a failed Prometheus query."""
    item_id = str(item.get("id") or item.get("name") or "item")
    name = str(item.get("name") or item_id)
    return ItemAnalysis(
        id=item_id,
        name=name,
        description=str(item.get("description") or ""),
        promql=str(item.get("promql") or item.get("query") or ""),
        unit=str(item.get("unit") or ""),
        severity="unknown",
        status=STATUS_BY_SEVERITY["unknown"],
        summary=f"Query failed: {message}",
        checked_series=0,
        returned_series=0,
        series=[],
    )


def _analyze_series(
    item: Mapping[str, object],
    series: TimeSeries,
    forecast_hours: float,
    min_points: int,
) -> SeriesAnalysis:
    points = sorted(series.points, key=lambda point: point.timestamp)
    values = [point.value for point in points if math.isfinite(point.value)]
    if len(values) < min_points:
        return SeriesAnalysis(
            labels=series.labels,
            display_name=series.display_name(),
            severity="unknown",
            status=STATUS_BY_SEVERITY["unknown"],
            reason=f"Only {len(values)} usable samples were returned.",
            current=values[-1] if values else None,
            average=_average(values),
            minimum=min(values) if values else None,
            maximum=max(values) if values else None,
            p95=_percentile(values, 95) if values else None,
            slope_per_hour=None,
            forecast=None,
            time_to_warning_hours=None,
            time_to_critical_hours=None,
            point_count=len(values),
        )

    current = values[-1]
    average = _average(values)
    minimum = min(values)
    maximum = max(values)
    p95 = _percentile(values, 95)
    slope_per_hour = _linear_slope_per_hour(points)
    forecast = current + slope_per_hour * forecast_hours
    current_severity = _threshold_severity(current, item)
    forecast_severity = _threshold_severity(forecast, item)
    time_to_warning = _time_to_threshold(current, slope_per_hour, _float_or_none(item.get("warning")), item)
    time_to_critical = _time_to_threshold(current, slope_per_hour, _float_or_none(item.get("critical")), item)
    severity, reason = _series_risk(
        item=item,
        current=current,
        forecast=forecast,
        current_severity=current_severity,
        forecast_severity=forecast_severity,
        slope_per_hour=slope_per_hour,
        forecast_hours=forecast_hours,
        time_to_warning=time_to_warning,
        time_to_critical=time_to_critical,
    )

    return SeriesAnalysis(
        labels=series.labels,
        display_name=series.display_name(),
        severity=severity,
        status=STATUS_BY_SEVERITY.get(severity, severity.title()),
        reason=reason,
        current=current,
        average=average,
        minimum=minimum,
        maximum=maximum,
        p95=p95,
        slope_per_hour=slope_per_hour,
        forecast=forecast,
        time_to_warning_hours=time_to_warning,
        time_to_critical_hours=time_to_critical,
        point_count=len(values),
    )


def _series_risk(
    item: Mapping[str, object],
    current: float,
    forecast: float,
    current_severity: str,
    forecast_severity: str,
    slope_per_hour: float,
    forecast_hours: float,
    time_to_warning: Optional[float],
    time_to_critical: Optional[float],
) -> Tuple[str, str]:
    severity = max_severity([current_severity, forecast_severity])
    unit = str(item.get("unit") or "")
    current_text = _format_value(current, unit)
    forecast_text = _format_value(forecast, unit)

    if current_severity in {"critical", "warning"}:
        return (
            current_severity,
            f"Current value is {current_text}, which is already {current_severity}.",
        )

    if forecast_severity in {"critical", "warning"}:
        crossing = _best_crossing_text(forecast_severity, time_to_warning, time_to_critical)
        return (
            forecast_severity,
            f"Forecast reaches {forecast_text} in {forecast_hours:g}h{crossing}.",
        )

    early_warning = _early_warning_reason(item, current, forecast, slope_per_hour, unit)
    if early_warning:
        return "info", early_warning

    return severity, f"Current value is {current_text}; forecast remains {forecast_text}."


def _threshold_severity(value: Optional[float], item: Mapping[str, object]) -> str:
    if value is None or not math.isfinite(value):
        return "unknown"
    direction = str(item.get("direction") or "higher_is_bad")
    warning = _float_or_none(item.get("warning"))
    critical = _float_or_none(item.get("critical"))
    if direction == "lower_is_bad":
        if critical is not None and value <= critical:
            return "critical"
        if warning is not None and value <= warning:
            return "warning"
        return "ok"
    if critical is not None and value >= critical:
        return "critical"
    if warning is not None and value >= warning:
        return "warning"
    return "ok"


def _time_to_threshold(
    current: float,
    slope_per_hour: float,
    threshold: Optional[float],
    item: Mapping[str, object],
) -> Optional[float]:
    if threshold is None or not math.isfinite(slope_per_hour) or slope_per_hour == 0:
        return None
    direction = str(item.get("direction") or "higher_is_bad")
    if direction == "lower_is_bad":
        if current <= threshold:
            return 0.0
        if slope_per_hour >= 0 or threshold >= current:
            return None
    else:
        if current >= threshold:
            return 0.0
        if slope_per_hour <= 0 or threshold <= current:
            return None
    hours = (threshold - current) / slope_per_hour
    if hours < 0 or not math.isfinite(hours):
        return None
    return hours


def _early_warning_reason(
    item: Mapping[str, object],
    current: float,
    forecast: float,
    slope_per_hour: float,
    unit: str,
) -> Optional[str]:
    direction = str(item.get("direction") or "higher_is_bad")
    warning = _float_or_none(item.get("warning"))
    if warning is None:
        return None

    if direction == "lower_is_bad":
        if slope_per_hour >= 0 or current <= warning:
            return None
        margin = current - warning
        consumed = current - forecast
    else:
        if slope_per_hour <= 0 or current >= warning:
            return None
        margin = warning - current
        consumed = forecast - current

    if margin <= 0:
        return None
    consumed_ratio = consumed / margin
    if consumed_ratio < 0.5:
        return None
    percent = consumed_ratio * 100
    return (
        f"Bad trend: forecast consumes {percent:.0f}% of the remaining warning margin "
        f"({ _format_value(current, unit) } -> { _format_value(forecast, unit) })."
    )


def _linear_slope_per_hour(points: Sequence[object]) -> float:
    if len(points) < 2:
        return 0.0
    first_ts = points[0].timestamp.timestamp()
    xs = [point.timestamp.timestamp() - first_ts for point in points]
    ys = [point.value for point in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator * 3600


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * percentile / 100
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _average(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _float_or_none(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _best_crossing_text(
    forecast_severity: str,
    time_to_warning: Optional[float],
    time_to_critical: Optional[float],
) -> str:
    if forecast_severity == "critical" and time_to_critical is not None:
        return f"; critical threshold in about {time_to_critical:.1f}h"
    if time_to_warning is not None:
        return f"; warning threshold in about {time_to_warning:.1f}h"
    return ""


def _format_value(value: Optional[float], unit: str = "") -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    if abs(value) >= 100:
        formatted = f"{value:.1f}"
    elif abs(value) >= 10:
        formatted = f"{value:.2f}"
    else:
        formatted = f"{value:.3f}"
    return f"{formatted}{unit}"


def _item_summary(severity: str, analyses: Sequence[SeriesAnalysis], total_series: int) -> str:
    if not analyses:
        return "No usable time series were available."
    worst = analyses[0]
    if severity == "ok":
        return f"All {total_series} series are within thresholds and forecast remains healthy."
    if severity == "info":
        return f"{worst.display_name}: {worst.reason}"
    if severity == "unknown":
        return f"{worst.display_name}: {worst.reason}"
    return f"{worst.display_name}: {worst.reason}"


def _series_sort_key(analysis: SeriesAnalysis) -> Tuple[int, float, float]:
    severity_rank = SEVERITY_ORDER.get(analysis.severity, -1)
    current = analysis.current if analysis.current is not None else float("-inf")
    forecast = analysis.forecast if analysis.forecast is not None else float("-inf")
    return severity_rank, abs(forecast), abs(current)
